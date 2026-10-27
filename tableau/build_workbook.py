"""Generate tableau/citibike_dashboard.twb: a Tableau workbook connected to the CSVs in data/marts/.

Run:  .venv/bin/python tableau/build_workbook.py
Open: double-click tableau/citibike_dashboard.twbx (Tableau Public / Desktop).
Tableau Public only accepts extracts, so every CSV is converted to a .hyper extract (Tableau Hyper API)
and packaged with the workbook XML into a .twbx (a zip file).
The workbook is plain XML; this script is the single source of truth for every sheet and dashboard.
"""
import os
import shutil
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import pandas as pd
from tableauhyperapi import (
    Connection,
    CreateMode,
    HyperProcess,
    Inserter,
    SqlType,
    TableDefinition,
    TableName,
    Telemetry,
)

ROOT = Path(__file__).resolve().parents[1]
MARTS = ROOT / "data" / "marts"
OUT = ROOT / "tableau" / "citibike_dashboard.twbx"
BUILD = ROOT / "tableau" / "build"
HYPER_TYPES = {"string": SqlType.text(), "integer": SqlType.big_int(), "real": SqlType.double(),
               "date": SqlType.date()}

DATE_COLS = {"date", "month_start", "observed_date"}
NUMERIC_DIMENSIONS = {"access_code", "freq_code", "reason_code", "days", "respondents_n"}
PERCENT_COLS = {"member_share", "trips_vs_baseline", "avg_trips_vs_baseline", "winter_to_summer_ratio",
                "ebike_share", "weighted_share", "weighted_share_of_non_users", "share_of_total",
                "net_growth_yoy", "net_growth_mom"}
MONEY_COLS = {"price_usd", "per_minute_usd", "annual_price", "day_pass_price"}
GEO = {"lat": "[Geographical].[Latitude]", "lng": "[Geographical].[Longitude]"}
CAPTIONS = {
    "city_id": "Market", "rider_type": "Rider type", "trips_vs_baseline": "Trips vs normal day",
    "avg_trips_vs_baseline": "Trips vs normal day", "tmax_c": "Max temperature (°C)", "rain_band": "Rain",
    "snow_day": "Snow day", "temp_band": "Temperature", "month_start": "Date", "total_trips": "Trips",
    "member_share": "Member share of trips", "winter_to_summer_ratio": "Winter trips as % of summer",
    "ride_year": "Ride year (Jul-Jun)", "observed_date": "Price observed", "price_usd": "Price (USD)",
    "plan_name": "Plan", "day_passes_to_break_even": "Day passes = 1 annual membership",
    "total_annual_members": "Annual members", "annual_signups_or_renewals": "Sign-ups or renewals",
    "amount_mtd_usd": "Revenue (USD)", "category": "Revenue category",
    "avg_handle_minutes": "Avg call handling time (min)", "calls_per_100_trips": "Support calls per 100 trips",
    "weighted_share": "Share (weighted)", "weighted_share_of_non_users": "Share of non-users (weighted)",
    "reason": "Reason", "frequency": "Frequency", "is_subscription": "Subscription?",
    "station_name": "Station", "member_trips": "Member trips", "ebike_share": "E-bike share of trips",
}
PALETTE = {  # fixed colours so a colour means the same thing on every chart
    "rider_type": {"member": "#1f4e79", "casual": "#e8833a"},
    "city_id": {"NYC": "#7b4fa0", "CHI": "#2a9d8f"},
    "is_subscription": {"Yes": "#1f4e79", "No": "#e8833a", "Not stated": "#a5a5a5"},
}
CA = {"remote": {"string": 129, "integer": 20, "real": 5, "date": 133}}


class DataSource:
    def __init__(self, file: str):
        self.file = file
        self.name = f"federated.{uuid.uuid4().hex[:28]}"
        self.conn = f"textscan.{uuid.uuid4().hex[:28]}"
        df = pd.read_csv(MARTS / f"{file}.csv", nrows=200)
        self.cols = {}
        for c, dt in df.dtypes.items():
            if c in DATE_COLS:
                t = "date"
            elif pd.api.types.is_bool_dtype(dt) or pd.api.types.is_object_dtype(dt) or pd.api.types.is_string_dtype(dt):
                t = "string"
            elif pd.api.types.is_integer_dtype(dt):
                t = "integer"
            else:
                t = "real"
            self.cols[c] = t

    def palette_style(self) -> str:
        rules = ""
        for col, colours in PALETTE.items():
            if col in self.cols:
                maps = "".join(f"<map to='{c}'><bucket>&quot;{v}&quot;</bucket></map>" for v, c in colours.items())
                rules += f"<encoding attr='color' field='[none:{col}:nk]' type='palette'>{maps}</encoding>"
        return f"<style><style-rule element='mark'>{rules}</style-rule></style>" if rules else ""

    def write_hyper(self, hyper: HyperProcess, folder: Path) -> None:
        df = pd.read_csv(MARTS / f"{self.file}.csv")
        table = TableDefinition(TableName("Extract", "Extract"),
                                [TableDefinition.Column(c, HYPER_TYPES[t]) for c, t in self.cols.items()])
        rows = []
        for rec in df.itertuples(index=False):
            row = []
            for (_c, t), v in zip(self.cols.items(), rec, strict=True):
                if pd.isna(v):
                    row.append(None)
                elif t == "date":
                    row.append(pd.Timestamp(v).date())
                elif t == "string":
                    row.append(str(v))
                elif t == "integer":
                    row.append(int(v))
                else:
                    row.append(float(v))
            rows.append(row)
        with Connection(hyper.endpoint, folder / f"{self.file}.hyper", CreateMode.CREATE_AND_REPLACE) as con:
            con.catalog.create_schema("Extract")
            con.catalog.create_table(table)
            with Inserter(con, table) as ins:
                ins.add_rows(rows)
                ins.execute()

    def ref(self, col: str, kind: str) -> str:
        return f"[{self.name}].[{instance_name(col, kind)}]"

    def xml(self) -> str:
        cols = "".join(f"<column datatype='{t}' name={quoteattr(c)} ordinal='{i}' />"
                       for i, (c, t) in enumerate(self.cols.items()))
        meta = "".join(
            f"<metadata-record class='column'><remote-name>{escape(c)}</remote-name>"
            f"<remote-type>{CA['remote'][t]}</remote-type><local-name>[{escape(c)}]</local-name>"
            f"<parent-name>[{self.file}.csv]</parent-name><remote-alias>{escape(c)}</remote-alias>"
            f"<ordinal>{i}</ordinal><local-type>{t}</local-type>"
            f"<aggregation>{'Sum' if t in ('integer', 'real') else 'Count'}</aggregation>"
            f"<contains-null>true</contains-null></metadata-record>"
            for i, (c, t) in enumerate(self.cols.items()))
        defs = []
        for c, t in self.cols.items():
            role, typ = column_role(c, t)
            attrs = f"datatype='{t}' name='[{c}]' role='{role}' type='{typ}'"
            if c in CAPTIONS:
                attrs = f"caption={quoteattr(CAPTIONS[c])} " + attrs
            if c in PERCENT_COLS:
                attrs += " default-format='p0%'"
            if c in MONEY_COLS:
                attrs += " default-format='c&quot;$&quot;#,##0.00'"
            if c in GEO:
                attrs = "aggregation='Avg' " + attrs + f" semantic-role='{GEO[c]}'"
            defs.append(f"<column {attrs} />")
        for c in self.cols:
            if c in PALETTE:
                defs.append(f"<column-instance column='[{c}]' derivation='None' name='[none:{c}:nk]' "
                            f"pivot='key' type='nominal' />")
        # relative and with forward slashes, so the workbook holds no absolute or Windows-style path
        marts_dir = Path(os.path.relpath(MARTS, ROOT)).as_posix()
        return (
            f"<datasource caption={quoteattr(self.file)} inline='true' name='{self.name}' version='18.1'>"
            f"<connection class='federated'><named-connections>"
            f"<named-connection caption={quoteattr(self.file)} name='{self.conn}'>"
            f"<connection class='textscan' directory={quoteattr(marts_dir)} filename='{self.file}.csv' "
            f"password='' server='' /></named-connection></named-connections>"
            f"<relation connection='{self.conn}' name='{self.file}.csv' table='[{self.file}#csv]' type='table'>"
            f"<columns character-set='UTF-8' header='yes' locale='en_US' separator=','>{cols}</columns>"
            f"</relation><metadata-records>{meta}</metadata-records></connection>"
            f"<aliases enabled='yes' />{''.join(defs)}"
            f"<extract count='-1' enabled='true' units='records'>"
            f"<connection access_mode='readonly' authentication='auth-none' author-locale='en_US' class='hyper' "
            f"dbname='Data/Extracts/{self.file}.hyper' default-settings='hyper' schema='Extract' sslmode='' "
            f"tablename='Extract' update-time='10/13/2026 07:00:00 PM' username='tableau_internal_user'>"
            f"<relation name='Extract' table='[Extract].[Extract]' type='table' />"
            f"<refresh increment-key='' incremental-updates='false' />"
            f"<metadata-records>{meta.replace(f'[{self.file}.csv]', '[Extract]')}</metadata-records>"
            f"</connection></extract>"
            f"<layout dim-ordering='alphabetic' dim-percentage='0.5' measure-ordering='alphabetic' "
            f"measure-percentage='0.4' show-structure='true' />"
            f"{self.palette_style()}"
            f"</datasource>"
        )


def column_role(col: str, t: str):
    if t in ("string",) or col in NUMERIC_DIMENSIONS:
        return "dimension", "nominal"
    if t == "date":
        return "dimension", "ordinal"
    return "measure", "quantitative"


KINDS = {  # kind -> (derivation, prefix, suffix, type)
    "dim": ("None", "none", "nk", "nominal"),
    "val": ("None", "none", "qk", "quantitative"),   # disaggregated continuous value
    "sum": ("Sum", "sum", "qk", "quantitative"),
    "avg": ("Avg", "avg", "qk", "quantitative"),
    "month": ("Month-Trunc", "tmn", "qk", "quantitative"),
    "day": ("Day-Trunc", "tdy", "qk", "quantitative"),
}


def instance_name(col: str, kind: str) -> str:
    _, prefix, suffix, _ = KINDS[kind]
    return f"{prefix}:{col}:{suffix}"


class Sheet:
    def __init__(self, name, title, ds, rows=(), cols=(), mark="Automatic", color=None, size=None,
                 detail=(), tooltip=(), text=None, filters=(), aggregate=True, sort=None, last_date=None,
                 skip_nulls=None):
        self.__dict__.update(locals())

    def fields(self):
        used = list(self.rows) + list(self.cols) + list(self.detail) + list(self.tooltip)
        used += [x for x in (self.color, self.size, self.text) if x]
        used += [(c, "dim") for c, _ in self.filters]
        if self.sort:
            used += [self.sort[0], self.sort[1]]
        if self.last_date:
            used.append(self.last_date[0])
        seen, out = set(), []
        for f in used:
            if f not in seen:
                seen.add(f), out.append(f)
        return out

    def shelf(self, items, joiner=" / "):
        refs = [self.ds.ref(c, k) for c, k in items]
        return "" if not refs else (refs[0] if len(refs) == 1 else "(" + joiner.join(refs) + ")")

    def is_map(self) -> bool:
        return {c for c, _ in self.rows} | {c for c, _ in self.cols} == {"lat", "lng"}

    def style(self) -> str:
        return "<style />"
        if not self.color or self.color[0] not in PALETTE:
            return "<style />"
        col = self.color[0]
        maps = "".join(f"<map to='{c}'><bucket>&quot;{v}&quot;</bucket></map>" for v, c in PALETTE[col].items())
        return (f"<style><style-rule element='mark'><encoding attr='color' field='{self.ds.ref(col, 'dim')}' "
                f"type='palette'>{maps}</encoding></style-rule></style>")

    def xml(self) -> str:
        ds = self.ds
        deps = []
        for col in sorted({c for c, _ in self.fields()}):
            role, typ = column_role(col, ds.cols[col])
            extra = f" semantic-role='{GEO[col]}'" if col in GEO else ""
            deps.append(f"<column datatype='{ds.cols[col]}' name='[{col}]' role='{role}' type='{typ}'{extra} />")
        for col, kind in self.fields():
            deriv, _, _, typ = KINDS[kind]
            deps.append(f"<column-instance column='[{col}]' derivation='{deriv}' "
                        f"name='[{instance_name(col, kind)}]' pivot='key' type='{typ}' />")
        filters, slices = "", ""
        for col, value in self.filters:
            ref = ds.ref(col, "dim")
            filters += (f"<filter class='categorical' column='{ref}'><groupfilter function='member' "
                        f"level='[{instance_name(col, 'dim')}]' member={quoteattr(chr(34) + value + chr(34))} "
                        f"user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate' />"
                        f"</filter>")
            slices += f"<column>{ref}</column>"
        if self.last_date:  # show dates up to and including this one
            (col, kind), day = self.last_date
            ref = ds.ref(col, kind)
            filters += (f"<filter class='quantitative' column='{ref}' included-values='in-range'>"
                        f"<max>#{day}#</max></filter>")
            slices += f"<column>{ref}</column>"
        if self.skip_nulls:  # leave out months with no value, so the line joins across them
            ref = ds.ref(*self.skip_nulls)
            filters += f"<filter class='quantitative' column='{ref}' included-values='non-null' />"
            slices += f"<column>{ref}</column>"
        sort = ""
        if self.sort:
            (dcol, dkind), (mcol, mkind) = self.sort
            sort = (f"<sort class='computed' column='{ds.ref(dcol, dkind)}' direction='DESC' "
                    f"using='{ds.ref(mcol, mkind)}' />")
        enc = ""
        if self.color:
            enc += f"<color column='{ds.ref(*self.color)}' />"
        if self.size:
            enc += f"<size column='{ds.ref(*self.size)}' />"
        if self.text:
            enc += f"<text column='{ds.ref(*self.text)}' />"
        for d in self.detail:
            enc += f"<lod column='{ds.ref(*d)}' />"
        for t in self.tooltip:
            enc += f"<tooltip column='{ds.ref(*t)}' />"
        mapsources = "<mapsources><mapsource name='Tableau' /></mapsources>" if self.is_map() else ""
        return (
            f"<worksheet name={quoteattr(self.name)}>"
            f"<layout-options><title><formatted-text><run fontsize='12' bold='true'>{escape(self.title)}</run>"
            f"</formatted-text></title></layout-options>"
            f"<table><view><datasources><datasource caption={quoteattr(ds.file)} name='{ds.name}' /></datasources>"
            f"{mapsources}"
            f"<datasource-dependencies datasource='{ds.name}'>{''.join(deps)}</datasource-dependencies>"
            f"{filters}{sort}"
            f"{'<slices>' + slices + '</slices>' if slices else ''}"
            f"<aggregation value='{'true' if self.aggregate else 'false'}' /></view>{self.style()}"
            f"<panes><pane selection-relaxation-option='selection-relaxation-allow'>"
            f"<view><breakdown value='auto' /></view><mark class='{self.mark}' />"
            f"{'<encodings>' + enc + '</encodings>' if enc else ''}</pane></panes>"
            f"<rows>{escape(self.shelf(self.rows))}</rows><cols>{escape(self.shelf(self.cols))}</cols>"
            f"</table></worksheet>"
        )


def text_runs(lines):
    out = []
    for i, (txt, style) in enumerate(lines):
        attrs = {"title": " bold='true' fontsize='18' fontcolor='#1f4e79'", "head": " bold='true' fontsize='11'",
                 "body": " fontsize='10'", "note": " fontsize='9' fontcolor='#555555' italic='true'"}[style]
        nl = "&#10;" if i < len(lines) - 1 else ""
        out.append(f"<run{attrs}>{escape(txt)}{nl}</run>")
    return "<formatted-text>" + "".join(out) + "</formatted-text>"


class Dashboard:
    """Vertical stack: title text, then rows of sheets (each row a horizontal container), then a note."""

    def __init__(self, name, title_lines, rows, note_lines, row_heights=None):
        self.__dict__.update(locals())

    def xml(self) -> str:
        zid = iter(range(2, 1000))
        H_TITLE, H_NOTE = 10000, 13000
        avail = 100000 - H_TITLE - H_NOTE
        heights = self.row_heights or [avail // len(self.rows)] * len(self.rows)
        inner, y = [], 0
        inner.append(f"<zone h='{H_TITLE}' id='{next(zid)}' type-v2='text' w='100000' x='0' y='0'>"
                     f"{text_runs(self.title_lines)}</zone>")
        y += H_TITLE
        for row, h in zip(self.rows, heights, strict=True):
            legends, seen = [], set()
            for s in row:  # one legend per colour field per row
                c = SHEETS[s].color
                if c and c[1] == "dim" and c[0] not in seen:
                    seen.add(c[0])
                    legends.append((s, SHEETS[s].ds.ref(*c)))
            lw = 9000 if legends else 0
            w = (100000 - lw) // len(row)
            sheets = "".join(f"<zone h='{h}' id='{next(zid)}' name={quoteattr(s)} w='{w}' x='{i * w}' y='{y}' />"
                             for i, s in enumerate(row))
            if legends:
                lh = h // len(legends)
                stack = "".join(f"<zone h='{lh}' id='{next(zid)}' name={quoteattr(s)} param='{ref}' type-v2='color' "
                                f"w='{lw}' x='{100000 - lw}' y='{y + k * lh}' />" for k, (s, ref) in enumerate(legends))
                sheets += (f"<zone h='{h}' id='{next(zid)}' param='vert' type-v2='layout-flow' w='{lw}' "
                           f"x='{100000 - lw}' y='{y}'>{stack}</zone>")
            inner.append(f"<zone h='{h}' id='{next(zid)}' param='horz' type-v2='layout-flow' w='100000' x='0' "
                         f"y='{y}'>{sheets}</zone>")
            y += h
        inner.append(f"<zone h='{H_NOTE}' id='{next(zid)}' type-v2='text' w='100000' x='0' y='{y}'>"
                     f"{text_runs(self.note_lines)}</zone>")
        return (
            f"<dashboard name={quoteattr(self.name)}><style />"
            f"<size maxheight='900' maxwidth='1400' minheight='900' minwidth='1400' sizing-mode='fixed' />"
            f"<datasources />"
            f"<zones><zone h='100000' id='1' type-v2='layout-basic' w='100000' x='0' y='0'>"
            f"<zone h='100000' id='999' param='vert' type-v2='layout-flow' w='100000' x='0' y='0'>"
            f"{''.join(inner)}</zone></zone></zones>"
            f"</dashboard>"
        )


SHEETS = {}


def build():
    D = {f: DataSource(f) for f in [
        "daily_weather_ridership", "weather_rain_effect", "weather_snow_effect", "city_monthly_engagement",
        "seasonality", "price_history", "price_breakeven", "nyc_monthly_kpis", "nyc_revenue_mix",
        "survey_plan_held", "survey_non_use_reasons", "survey_frequency", "station_activity", "ebike_share"]}
    w, r, s = D["daily_weather_ridership"], D["weather_rain_effect"], D["weather_snow_effect"]
    cm, se, ph, pb = D["city_monthly_engagement"], D["seasonality"], D["price_history"], D["price_breakeven"]
    k, rv = D["nyc_monthly_kpis"], D["nyc_revenue_mix"]
    sp, sr, sf, st, eb = (D["survey_plan_held"], D["survey_non_use_reasons"], D["survey_frequency"],
                          D["station_activity"], D["ebike_share"])
    RT = ("rider_type", "dim")
    CITY = ("city_id", "dim")
    sheets = [
        Sheet("Weather - temperature", "Each day: trips vs a normal day, by max temperature", w,
              rows=[("trips_vs_baseline", "val")], cols=[CITY, ("tmax_c", "val")], mark="Circle", color=RT,
              detail=[("date", "dim")], filters=[("is_holiday", "False")], aggregate=False),
        Sheet("Weather - rain", "Rain: trips vs a normal day (1.0 = normal)", r,
              rows=[("avg_trips_vs_baseline", "avg")], cols=[CITY, ("rain_band", "dim"), RT], mark="Bar", color=RT),
        Sheet("Weather - snow", "Winter days: snow vs no snow", s,
              rows=[("avg_trips_vs_baseline", "avg")], cols=[CITY, ("snow_day", "dim"), RT], mark="Bar", color=RT),
        Sheet("Cities - monthly trips", "Monthly trips: NYC vs Chicago", cm,
              rows=[("total_trips", "sum")], cols=[("month_start", "month")], mark="Line", color=CITY),
        Sheet("Cities - member share", "Member share of trips", cm,
              rows=[("member_share", "avg")], cols=[("month_start", "month")], mark="Line", color=CITY),
        Sheet("Seasons - winter vs summer", "Winter riding as % of summer (Dec-Feb / Jun-Aug)", se,
              rows=[("winter_to_summer_ratio", "avg")], cols=[CITY, RT, ("ride_year", "dim")], mark="Bar",
              color=RT),
        Sheet("Price - annual", "Annual membership price (USD), one dot per observation", ph,
              rows=[("price_usd", "avg")], cols=[("observed_date", "day")], mark="Circle", color=CITY,
              filters=[("plan_name", "Annual Membership")]),
        Sheet("Price - break-even", "How many day passes cost the same as one annual membership", pb,
              rows=[("day_passes_to_break_even", "avg")], cols=[CITY, ("observed_date", "dim")], mark="Bar",
              color=CITY),
        Sheet("Price - all plans", "All plan prices (USD) by observation date", ph,
              rows=[CITY, ("plan_name", "dim")], cols=[("observed_date", "dim")], mark="Text",
              text=("price_usd", "avg")),
        Sheet("NYC - members", "NYC annual members (end of month; Feb and May 2026 not published)", k,
              rows=[("total_annual_members", "avg")], cols=[("month_start", "month")], mark="Line",
              skip_nulls=("total_annual_members", "avg")),
        Sheet("NYC - sign-ups", "NYC annual sign-ups or renewals per month", k,
              rows=[("annual_signups_or_renewals", "sum")], cols=[("month_start", "month")], mark="Bar"),
        Sheet("NYC - revenue mix",
              "NYC revenue by category (USD, before tax, preliminary; Feb and May 2026 calculated)", rv,
              rows=[("amount_mtd_usd", "sum")], cols=[("month_start", "month")], mark="Bar",
              color=("category", "dim")),
        Sheet("NYC - handling time", "NYC average call handling time (minutes), to Jan 2026", k,
              rows=[("avg_handle_minutes", "avg")], cols=[("month_start", "month")], mark="Line",
              last_date=(("month_start", "month"), "2026-01-01")),
        Sheet("NYC - calls per 100 trips", "NYC support calls per 100 trips", k,
              rows=[("calls_per_100_trips", "avg")], cols=[("month_start", "month")], mark="Line"),
        Sheet("Survey - plan used", "How Citi Bike users last accessed it (2024, weighted)", sp,
              rows=[("plan_name", "dim")], cols=[("weighted_share", "sum")], mark="Bar",
              color=("is_subscription", "dim"), sort=(("plan_name", "dim"), ("weighted_share", "sum"))),
        Sheet("Survey - reasons", "Why cyclists don't use Citi Bike (2024, weighted)", sr,
              rows=[("reason", "dim")], cols=[("weighted_share_of_non_users", "sum")], mark="Bar",
              sort=(("reason", "dim"), ("weighted_share_of_non_users", "sum"))),
        Sheet("Survey - frequency", "How often cyclists use Citi Bike (2024, weighted)", sf,
              rows=[("frequency", "dim")], cols=[("weighted_share", "sum")], mark="Bar"),
        Sheet("Map - NYC", "NYC stations: size = trips, colour = member share", st,
              rows=[("lat", "avg")], cols=[("lng", "avg")], mark="Circle", color=("member_share", "avg"),
              size=("total_trips", "sum"), detail=[("station_key", "dim"), ("station_name", "dim")],
              filters=[("city_id", "NYC")]),
        Sheet("Map - Chicago", "Chicago stations: size = trips, colour = member share", st,
              rows=[("lat", "avg")], cols=[("lng", "avg")], mark="Circle", color=("member_share", "avg"),
              size=("total_trips", "sum"), detail=[("station_key", "dim"), ("station_name", "dim")],
              filters=[("city_id", "CHI")]),
        Sheet("E-bikes - share", "E-bike share of trips (sample months)", eb,
              rows=[("ebike_share", "avg")], cols=[CITY, RT], mark="Bar", color=RT),
    ]
    SHEETS.update({x.name: x for x in sheets})
    SRC = ("Sources: Citi Bike, Divvy (Lyft); U.S. Bureau of Transportation Statistics; NOAA; NYC DOT. "
           "Jul 2023 - Jun 2026.")
    dashboards = [
        Dashboard("1 Overview",
                  [("Citi Bike as a Subscription Business: NYC vs Chicago", "title"),
                   ("Members are the stable base: they ride more, in all weather, all year.", "body")],
                  [["NYC - members", "Cities - member share"], ["Seasons - winter vs summer", "Weather - rain"]],
                  [("Members make 81-83% of NYC trips vs 64-65% in Chicago. Casual riders drop more in bad weather "
                    "and in winter.", "head"), ("Associations, not causes. " + SRC, "note")]),
        Dashboard("2 Weather",
                  [("Weather: casual riders are more sensitive than members", "title"),
                   ("Each day compared with a normal day for the same city, rider type, month and weekday type.",
                    "body")],
                  [["Weather - temperature"], ["Weather - rain", "Weather - snow"]],
                  [("Heavy rain: NYC casual -45% vs members -37%; Chicago casual -36% vs members -29% "
                    "(vs a dry day).", "head"), ("Associations, not causes. Holidays excluded. " + SRC, "note")]),
        Dashboard("3 Seasons & Cities",
                  [("Seasons and cities: Chicago's winter drop is deeper", "title"),
                   ("Monthly trips and member share, Jul 2023 - Jun 2026.", "body")],
                  [["Cities - monthly trips", "Cities - member share"], ["Seasons - winter vs summer"]],
                  [("In winter, Chicago casual riding falls to 10-13% of summer; NYC members keep 39-57%.", "head"),
                   ("Chicago from Divvy trip files (BTS double-counts Jan 2026); NYC from BTS. " + SRC, "note")]),
        Dashboard("4 Price",
                  [("Price: NYC membership costs more, yet NYC has more members", "title"),
                   ("Annual membership and pay-as-you-go prices, from official pricing pages and archived snapshots.",
                    "body")],
                  [["Price - annual", "Price - break-even"], ["Price - all plans"]],
                  [("NYC single ride: flat $4.49-$4.99. Chicago: $1 + $0.18-0.20 per minute, so short casual rides "
                    "are cheaper there.", "head"),
                   ("Prices are snapshot observations; exact change dates unknown except NYC $239 from 28 Jan 2026. "
                    + SRC, "note")]),
        Dashboard("5 NYC Business KPIs",
                  [("NYC business KPIs: acquisition, retention, monetization, satisfaction", "title"),
                   ("From Citi Bike's monthly operating reports to NYC DOT.", "body")],
                  [["NYC - members", "NYC - sign-ups"], ["NYC - revenue mix", "NYC - handling time"]],
                  [("Members grew to 138,055 (Jun 2026). Call handling time rose from about 6 minutes to 18.6 in "
                    "Jan 2026; later reports show 17.3 (Mar), 14.4 (Apr) and 10.9 (Jun).", "head"),
                   ("Feb and May 2026 reports not published: members and sign-ups blank; revenue calculated from the "
                    "year-to-date totals in the Jan/Mar and Apr/Jun reports. From Mar 2025 report trips include "
                    "Jersey City. Revenue preliminary and unaudited. " + SRC, "note")]),
        Dashboard("6 Customers & Map",
                  [("Customers and stations", "title"),
                   ("NYC DOT survey 2024 (cyclists only, weighted) and station activity (sample months).", "body")],
                  [["Survey - plan used", "Survey - reasons", "E-bikes - share"], ["Map - NYC", "Map - Chicago"]],
                  [("44% of Citi Bike users hold a subscription; 'too expensive' is cited by 35% of cyclists who "
                    "don't use it.", "head"),
                   ("Survey covers adults who cycle (about 34% of adults). " + SRC, "note")]),
    ]
    cards = ("<cards><edge name='left'><strip size='160'><card type='pages' /><card type='filters' />"
             "<card type='marks' /></strip></edge><edge name='top'><strip size='2147483647'>"
             "<card type='columns' /></strip><strip size='2147483647'><card type='rows' /></strip>"
             "<strip size='31'><card type='title' /></strip></edge></cards>")
    wins = [("dashboard", d.name) for d in dashboards] + [("worksheet", x.name) for x in sheets]
    focus = wins[0][1]  # the workbook opens on the first dashboard
    dash_sheets = {d.name: [x for row in d.rows for x in row] for d in dashboards}

    def window(cls, name):
        mx = " maximized='true'" if name == focus else ""
        if cls == "dashboard":
            vps = "".join(f"<viewpoint name={quoteattr(x)}><zoom type='entire-view' /></viewpoint>"
                          for x in dash_sheets[name])
            body = f"<viewpoints>{vps}</viewpoints><active id='-1' /><device-preview visible='false' />"
        else:
            body = cards + "<viewpoint><zoom type='entire-view' /></viewpoint>"
        return f"<window class='{cls}'{mx} name={quoteattr(name)}>{body}</window>"
    windows = "".join(window(c, n) for c, n in wins)
    xml = (
        "<?xml version='1.0' encoding='utf-8' ?>\n"
        "<workbook original-version='18.1' source-build='2024.2.0 (20242.24.0716.1944)' source-platform='mac' "
        "version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>"
        f"<datasources>{''.join(d.xml() for d in D.values())}</datasources>"
        "<mapsources><mapsource name='Tableau' /></mapsources>"
        f"<worksheets>{''.join(x.xml() for x in sheets)}</worksheets>"
        f"<dashboards>{''.join(d.xml() for d in dashboards)}</dashboards>"
        f"<windows source-height='30'>{windows}</windows>"
        "</workbook>\n"
    )
    shutil.rmtree(BUILD, ignore_errors=True)
    extracts = BUILD / "Data" / "Extracts"
    extracts.mkdir(parents=True)
    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU, parameters={"log_dir": str(BUILD)}) as hyper:
        for d in D.values():
            d.write_hyper(hyper, extracts)
    (BUILD / "citibike_dashboard.twb").write_text(xml, encoding="utf-8")
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(BUILD / "citibike_dashboard.twb", "citibike_dashboard.twb")
        for h in sorted(extracts.glob("*.hyper")):
            z.write(h, f"Data/Extracts/{h.name}")
    shutil.rmtree(BUILD)
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e6:.1f} MB): {len(D)} data sources (extracts), "
          f"{len(sheets)} sheets, {len(dashboards)} dashboards")


if __name__ == "__main__":
    build()
