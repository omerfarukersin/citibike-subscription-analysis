"""Library of chart builders used by build_story.py (data sources, sheets, marks, palette).
`main()` builds an optional gallery workbook, tableau/citibike_gallery.twbx (one sheet per chart).

Run:  .venv/bin/python tableau/build_gallery.py
List: .venv/bin/python tableau/build_gallery.py --list   (sheet names)

Reuses build_workbook.py (Hyper extracts, palette, packaging) and build_interactive.py (calculated fields).
A few charts need the data in long format (one row per rider type or bike type) or a 100-cell grid (waffle).
Those reshaped tables are written to tableau/gallery_data/ by this script from the CSVs in data/marts/;
no values are added or changed, only rearranged (the waffle rounds shares to whole squares, see waffle()).
"""
import re
import shutil
import sys
import zipfile
from contextlib import contextmanager
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import pandas as pd
from tableauhyperapi import HyperProcess, Telemetry

import build_workbook as bw
from build_interactive import CalcSource

ROOT = Path(__file__).resolve().parents[1]
MARTS = ROOT / "data" / "marts"
GDATA = ROOT / "tableau" / "gallery_data"
OUT = ROOT / "tableau" / "citibike_gallery.twbx"
BUILD = ROOT / "tableau" / "build_gallery"

DIVERGING = ["#b2182b", "#f7f7f7", "#2166ac"]   # red = below normal, blue = above normal
SEQ_BLUE = ["#dbe9f6", "#1f4e79"]
SEQ_ORANGE = ["#fde9d9", "#c55a11"]
EXTRA_PALETTES = {
    "charge_type": {"Paid per ride": "#2a9d8f", "Paid per year": "#1f4e79", "Other": "#bdbdbd", "Refunds": "#b2182b"},
    "condition": {"1 Dry": "#9ecae1", "2 Light (<5 mm)": "#6baed6", "3 Moderate (5-20 mm)": "#3182bd",
                  "4 Heavy (20+ mm)": "#08519c", "5 Snow day": "#7f7f7f"},
    "day_reason": {"Snow": "#7f7f7f", "Heavy rain": "#08519c", "Holiday": "#e9c46a",
                   "Deep cold (max below -5°C)": "#6a51a3", "Other": "#bdbdbd"},
    "plan_type": {"Subscription": "#1f4e79", "Pay as you go": "#e8833a"},
    "flow": {"Adds revenue": "#2a9d8f", "Refunds & discounts": "#b2182b"},
    "net_dir": {"Members up": "#1f4e79", "Members down": "#b2182b"},
    "bike": {"E-bike": "#6a994e", "Classic bike": "#9e9e9e"},
    "group": {"Never used": "#d9d9d9", "Used before, not in last 12 months": "#a5a5a5",
              "Less than monthly": "#f4b183", "At least monthly": "#e8833a", "At least weekly": "#2e75b6",
              "5+ days a week": "#1f4e79"},
}

bw.CAPTIONS.update({
    "trips_per_member": "Trips per member", "rider_revenue_per_trip": "Rider revenue per trip (USD)",
    "net_change_mom": "Net change in members", "avg_min": "Average trip (minutes)",
    "median_min": "Median trip (minutes)", "bike": "Bike type", "group": "How often they use Citi Bike",
    "trips": "Trips", "annual_price": "Annual price (USD)", "day_pass_price": "Day pass (USD)",
    "tmax_c": "Max temperature (°C)", "precip_mm": "Rain (mm)", "snow_mm": "Snow (mm)",
})

KINDS = dict(bw.KINDS,
             usr=("User", "usr", "qk", "quantitative"),
             max=("Max", "max", "qk", "quantitative"),
             dom=("Day", "dy", "ok", "ordinal"),        # day of month 1-31
             wd=("Weekday", "wd", "ok", "ordinal"),
             mn=("Month", "mn", "ok", "ordinal"),       # month name, all years together
             yr=("Year", "yr", "ok", "ordinal"),
             wk=("Week", "wk", "ok", "ordinal"),        # week of the year
             usrs=("User", "usr", "nk", "nominal"),     # calculated text, e.g. a label
             cntd=("CountD", "ctd", "qk", "quantitative"),  # count of distinct values
             my=("Month-Trunc", "tmn", "ok", "ordinal"))  # discrete month + year
MEASURE_KINDS = {"sum", "avg", "usr", "max", "val"}


def inst(col, kind):
    _, prefix, suffix, _ = KINDS[kind]
    return f"{prefix}:{col}:{suffix}"


@contextmanager
def marts_folder(folder):
    """bw.DataSource reads bw.MARTS; point it at another folder for the reshaped gallery tables."""
    old = bw.MARTS
    bw.MARTS = folder
    try:
        yield
    finally:
        bw.MARTS = old


class GSource(CalcSource):
    """A mart CSV (or a reshaped table written to gallery_data/) with calculated fields and extra palettes."""

    def __init__(self, file, calcs=None, df=None, formats=None):
        self.folder = MARTS
        self.formats = formats or {}
        if df is not None:
            GDATA.mkdir(exist_ok=True)
            df.to_csv(GDATA / f"{file}.csv", index=False)
            self.folder = GDATA
        with marts_folder(self.folder):
            super().__init__(file, calcs or {})

    def write_hyper(self, hyper, folder):
        with marts_folder(self.folder):
            super().write_hyper(hyper, folder)

    def palette_style(self):
        rules = ""
        names = set(self.cols) | set(self.calcs)
        for col, colours in {**bw.PALETTE, **EXTRA_PALETTES}.items():
            if col in names:
                maps = "".join(f"<map to='{c}'><bucket>&quot;{escape(v)}&quot;</bucket></map>"
                               for v, c in colours.items())
                rules += f"<encoding attr='color' field='[none:{col}:nk]' type='palette'>{maps}</encoding>"
        return f"<style><style-rule element='mark'>{rules}</style-rule></style>" if rules else ""

    def xml(self):
        with marts_folder(self.folder):
            base = bw.DataSource.xml(self)
        for col, fmt in self.formats.items():  # replaces bw's default format where it set one
            head = f"name='[{col}]' role='measure' type='quantitative'"
            repl = head + f" default-format={quoteattr(fmt)}"
            base = re.sub(re.escape(head) + r"( default-format='[^']*')?", lambda _m, r=repl: r, base)
        defs = "".join(calc_column(n, c) for n, c in self.calcs.items())
        insts = "".join(f"<column-instance column='[{c}]' derivation='None' name='[none:{c}:nk]' pivot='key' "
                        f"type='nominal' />" for c in EXTRA_PALETTES if c in self.calcs or c in self.cols)
        anchor = "<column-instance " if "<column-instance " in base else "<extract "
        return base.replace(anchor, defs + insts + anchor, 1)


def calc_column(name, c):
    fmt = f" default-format={quoteattr(c['fmt'])}" if c.get("fmt") else ""
    geo = f" semantic-role='{c['geo']}'" if c.get("geo") else ""
    return (f"<column caption={quoteattr(c['caption'])} datatype='{c['datatype']}' name='[{name}]' "
            f"role='{c['role']}' type='{c['type']}'{fmt}{geo}><calculation class='tableau' "
            f"formula={quoteattr(c['formula'])} /></column>")


def measure(caption, formula, fmt=None):
    return dict(caption=caption, datatype="real", role="measure", type="quantitative", formula=formula, fmt=fmt)


def dimension(caption, formula, datatype="string"):
    return dict(caption=caption, datatype=datatype, role="dimension", type="nominal", formula=formula)


def cont_dim(caption, formula, geo=None):
    return dict(caption=caption, datatype="real", role="dimension", type="quantitative", formula=formula, geo=geo)


def flag(caption, formula):
    return dimension(caption, formula, datatype="boolean")


class Layer:
    """What one pane draws: mark type and the fields on the Marks card."""

    def __init__(self, mark="Automatic", color=None, size=None, text=None, detail=(), tooltip=(), path=None,
                 labels=False, mark_color=None, mark_size=None, markers=False):
        self.__dict__.update(locals())

    def fields(self):
        return [x for x in (self.color, self.size, self.text, self.path) if x] + list(self.detail) + \
            list(self.tooltip)

    def xml(self, ref, attrs=""):
        enc = ""
        if self.color:
            enc += f"<color column='{ref(*self.color)}' />"
        if self.size:
            enc += f"<size column='{ref(*self.size)}' />"
        if self.text:
            enc += f"<text column='{ref(*self.text)}' />"
        if self.path:
            enc += f"<path column='{ref(*self.path)}' />"
        for d in self.detail:
            enc += f"<lod column='{ref(*d)}' />"
        for t in self.tooltip:
            enc += f"<tooltip column='{ref(*t)}' />"
        fmt = ""
        if self.labels:
            fmt += "<format attr='mark-labels-show' value='true' /><format attr='mark-labels-cull' value='false' />"
        if self.mark_color:
            fmt += f"<format attr='mark-color' value='{self.mark_color}' />"
        if self.mark_size is not None:
            fmt += f"<format attr='size' value='{self.mark_size}' />"
        if self.markers:
            fmt += "<format attr='mark-markers-mode' value='all' />"
        style = f"<style><style-rule element='mark'>{fmt}</style-rule></style>" if fmt else ""
        return (f"<pane{attrs} selection-relaxation-option='selection-relaxation-allow'>"
                f"<view><breakdown value='auto' /></view><mark class='{self.mark}' />"
                f"{'<encodings>' + enc + '</encodings>' if enc else ''}{style}</pane>")


class Sheet:
    """rows/cols: list of (column, kind); a nested list on a shelf means several measures side by side (+).
    dual='rows'|'cols' folds the two measures of that shelf onto one axis, drawn by layers[0] and layers[1]."""

    def __init__(self, name, title, ds, rows=(), cols=(), layers=(), filters=(), keep=(), sort=None,
                 color_scale=None, fontsize=None, formats=(), dual=None, is_map=False,
                 font_color="#1f4e79"):
        self.__dict__.update(locals())
        self.layers = list(layers) or [Layer()]

    @property
    def color(self):  # used by bw.Dashboard to add a legend for a colour dimension
        return self.layers[-1].color

    def ref(self, col, kind):
        return f"[{self.ds.name}].[{inst(col, kind)}]"

    def flat(self, shelf):
        out = []
        for item in shelf:
            out += item if isinstance(item, list) else [item]
        return out

    def fields(self):
        used = self.flat(self.rows) + self.flat(self.cols)
        for layer in self.layers:
            used += layer.fields()
        used += [(c, "dim") for c, _ in self.filters] + [(k, "dim") for k in self.keep]
        if self.sort:
            used += [self.sort[0], self.sort[1]]
        out = []
        for f in used:
            if f not in out:
                out.append(f)
        return out

    def shelf(self, items):
        parts = []
        for item in items:
            if isinstance(item, list):
                parts.append("(" + " + ".join(self.ref(*m) for m in item) + ")")
            else:
                parts.append(self.ref(*item))
        return "" if not parts else (parts[0] if len(parts) == 1 else "(" + " / ".join(parts) + ")")

    def deps(self):
        ds, cols = self.ds, []
        todo = [c for c, _ in self.fields()]
        while todo:  # calculated fields pull in the columns their formulas use
            c = todo.pop(0)
            if c in cols:
                continue
            cols.append(c)
            if c in ds.calcs:
                todo += [n for n in list(ds.calcs) + list(ds.cols) if f"[{n}]" in ds.calcs[c]["formula"]]
        out = []
        for c in cols:
            if c in ds.calcs:
                out.append(calc_column(c, ds.calcs[c]))
            else:
                role, typ = bw.column_role(c, ds.cols[c])
                geo = f" semantic-role='{bw.GEO[c]}'" if c in bw.GEO else ""
                out.append(f"<column datatype='{ds.cols[c]}' name='[{c}]' role='{role}' type='{typ}'{geo} />")
        for col, kind in self.fields():
            deriv, _, _, typ = KINDS[kind]
            out.append(f"<column-instance column='[{col}]' derivation='{deriv}' name='[{inst(col, kind)}]' "
                       f"pivot='key' type='{typ}' />")
        return "".join(out)

    def table_style(self):
        mark, cell, axis = "", "", ""
        if self.color_scale:
            field, kind, colours = self.color_scale
            ptype = "ordered-diverging" if len(colours) == 3 else "ordered-sequential"
            mark = (f"<encoding attr='color' field='{self.ref(*field)}' type='custom-interpolated'>"
                    f"<color-palette custom='true' name='' type='{ptype}'>"
                    f"{''.join(f'<color>{c}</color>' for c in colours)}</color-palette></encoding>")
        if self.fontsize:
            cell += f"<format attr='font-size' value='{self.fontsize}' /><format attr='font-weight' value='bold' />"
            if self.font_color:
                cell += f"<format attr='color' value='{self.font_color}' />"
        for col, kind, fmt in self.formats:
            cell += f"<format attr='text-format' field='{self.ref(col, kind)}' value={quoteattr(fmt)} />"
            axis += f"<format attr='text-format' field='{self.ref(col, kind)}' value={quoteattr(fmt)} />"
        if self.dual:
            m = self.flat(self.rows if self.dual == "rows" else self.cols)[-1]
            axis += (f"<encoding attr='space' class='0' field='{self.ref(*m)}' field-type='quantitative' fold='true' "
                     f"scope='{self.dual}' synchronized='true' type='space' />")
        rules = (f"<style-rule element='mark'>{mark}</style-rule>" if mark else "") + \
                (f"<style-rule element='cell'>{cell}</style-rule>" if cell else "") + \
                (f"<style-rule element='axis'>{axis}</style-rule>" if axis else "")
        return f"<style>{rules}</style>" if rules else "<style />"

    def panes(self):
        if not self.dual:
            return self.layers[0].xml(self.ref)
        m1, m2 = (self.ref(*x) for x in self.flat(self.rows if self.dual == "rows" else self.cols)[-2:])
        ax = "y" if self.dual == "rows" else "x"
        return (Layer().xml(self.ref) +
                self.layers[0].xml(self.ref, f" id='1' {ax}-axis-name='{m1}'") +
                self.layers[1].xml(self.ref, f" id='2' {ax}-axis-name='{m2}'"))

    def xml(self):
        ds = self.ds
        filters, slices = "", ""
        for col, value in list(self.filters) + [(k, "true") for k in self.keep]:
            r = self.ref(col, "dim")
            member = value if value in ("true", "false") else chr(34) + value + chr(34)
            filters += (f"<filter class='categorical' column='{r}'><groupfilter function='member' "
                        f"level='[{inst(col, 'dim')}]' member={quoteattr(member)} user:ui-domain='database' "
                        f"user:ui-enumeration='inclusive' user:ui-marker='enumerate' /></filter>")
            slices += f"<column>{r}</column>"
        sort = ""
        if self.sort:
            d, m, direction = self.sort
            sort = f"<sort class='computed' column='{self.ref(*d)}' direction='{direction}' using='{self.ref(*m)}' />"
        maps = "<mapsources><mapsource name='Tableau' /></mapsources>" if self.is_map else ""
        return (
            f"<worksheet name={quoteattr(self.name)}><layout-options><title><formatted-text>"
            f"<run fontsize='12' bold='true'>{escape(self.title)}</run></formatted-text></title></layout-options>"
            f"<table><view><datasources><datasource caption={quoteattr(ds.file)} name='{ds.name}' /></datasources>"
            f"{maps}<datasource-dependencies datasource='{ds.name}'>{self.deps()}</datasource-dependencies>"
            f"{filters}{sort}{'<slices>' + slices + '</slices>' if slices else ''}"
            f"<aggregation value='true' /></view>{self.table_style()}<panes>{self.panes()}</panes>"
            f"<rows>{escape(self.shelf(self.rows))}</rows><cols>{escape(self.shelf(self.cols))}</cols>"
            f"</table></worksheet>"
        )


# ── Reshaped tables (long format) ─────────────────────────────────────────────
def long_city_monthly():
    df = pd.read_csv(MARTS / "city_monthly_engagement.csv")
    out = df.melt(id_vars=["city_id", "year_month", "month_start", "member_share"],
                  value_vars=["member_trips", "casual_trips"], var_name="rider_type", value_name="trips")
    out["rider_type"] = out["rider_type"].str.replace("_trips", "")
    return out


def long_city_comparison():
    df = pd.read_csv(MARTS / "city_comparison.csv")
    out = df.melt(id_vars=["city_id", "ride_year", "member_share"], value_vars=["member_avg_min", "casual_avg_min"],
                  var_name="rider_type", value_name="avg_min")
    out["rider_type"] = out["rider_type"].str.replace("_avg_min", "")
    return out


def long_ebike():
    df = pd.read_csv(MARTS / "ebike_share.csv")
    out = df.melt(id_vars=["city_id", "year_month", "rider_type"],
                  value_vars=["ebike_median_min", "classic_median_min"], var_name="bike", value_name="median_min")
    out["bike"] = out["bike"].map({"ebike_median_min": "E-bike", "classic_median_min": "Classic bike"})
    return out


def waffle():
    """100 squares split by weighted share. Whole squares by the largest-remainder method, so they add to 100."""
    df = pd.read_csv(MARTS / "survey_frequency.csv").sort_values("freq_code")
    short = {1: "Never used", 2: "Used before, not in last 12 months", 3: "Less than monthly",
             4: "At least monthly", 5: "At least weekly", 6: "5+ days a week"}
    raw = df["weighted_share"] / df["weighted_share"].sum() * 100
    n = raw.astype(int)
    for i in (raw - n).sort_values(ascending=False).index[: 100 - n.sum()]:
        n[i] += 1
    rows, cell = [], 0
    for (_, r), k in zip(df.iterrows(), n, strict=True):
        for _ in range(k):
            rows.append(dict(cell=f"c{cell:02d}", x=cell % 10, y=9 - cell // 10, group=short[r.freq_code],
                             frequency=r.frequency, weighted_share=r.weighted_share))
            cell += 1
    return pd.DataFrame(rows)


def build():
    RT, CITY = ("rider_type", "dim"), ("city_id", "dim")
    pct = "p0%"
    w = GSource("daily_weather_ridership", {
        "base_trips": measure("Trips on a normal day", "[trips] / [trips_vs_baseline]"),
        "day_vs_normal": measure("Day vs normal (all riders)",
                                 "{FIXED [city_id], [date]: SUM([trips])} / "
                                 "{FIXED [city_id], [date]: SUM([base_trips])} - 1", pct),
        "vs_normal": measure("Trips vs normal day", "AVG([trips_vs_baseline]) - 1", pct),
        "worst_day": flag("Under 25% of normal", "[day_vs_normal] < -0.75"),
        "day_reason": dimension("Weather that day",
                                'IF [snow_mm] > 0 THEN "Snow" ELSEIF [is_holiday] = "True" THEN "Holiday" '
                                'ELSEIF [precip_mm] >= 20 THEN "Heavy rain" '
                                'ELSEIF [tmax_c] < -5 THEN "Deep cold (max below -5°C)" ELSE "Other" END'),
        "condition": dimension("Weather", 'IF [snow_day] = "True" THEN "5 Snow day" ELSE [rain_band] END'),
        "temp_step": cont_dim("Max temperature (2°C steps)", "ROUND([tmax_c] / 2) * 2"),
        "rider_base": measure("Average day for rider type",
                              "{FIXED [city_id], [rider_type]: SUM([trips]) / COUNTD([date])}"),
        "grid_index": measure("vs average day", "(SUM([trips]) / COUNTD([date])) / AVG([rider_base]) - 1", pct),
        "temp_index": measure("Trips vs average day", "AVG([trips]) / AVG([rider_base])", pct),
    })
    rain = GSource("weather_rain_effect", {
        "rain_vs": measure("Trips vs normal day", "AVG([avg_trips_vs_baseline]) - 1", pct)})
    cm = GSource("g_city_monthly_long", {
        "signed_trips": measure("Trips (casual shown below zero)", 'IIF([rider_type] = "casual", -[trips], [trips])'),
        "cal_year": dimension("Calendar year", "STR(YEAR([month_start]))"),
    }, df=long_city_monthly())
    cc = GSource("g_city_comparison_long", {
        "avg_min2": measure("Average trip (minutes)", "AVG([avg_min])", "n#,##0.0"),
    }, df=long_city_comparison(), formats={"avg_min": "n#,##0.0", "member_share": "p0.0%"})
    se = GSource("seasonality")
    latest = "[observed_date] = {FIXED [city_id]: MAX([observed_date])}"
    ph = GSource("price_history", {
        "latest": flag("Latest observation", latest),
        "plan_type": dimension("Plan type", 'IIF([is_subscription] = "True", "Subscription", "Pay as you go")'),
    })
    pb = GSource("price_breakeven", {"latest": flag("Latest observation", latest)},
                 formats={"day_passes_to_break_even": "n#,##0.0"})
    k = GSource("nyc_monthly_kpis", {
        "net_dir": dimension("Direction", 'IF ISNULL([net_change_mom]) THEN NULL ELSEIF [net_change_mom] >= 0 '
                                          'THEN "Members up" ELSE "Members down" END'),
        "has_net": flag("Has net change", "NOT ISNULL([net_change_mom])"),
        "published": flag("Report published", "NOT ISNULL([total_annual_members])"),
        "handle_to_jan": measure("Call handling (min), to Jan 2026",
                                 "IIF([month_start] <= #2026-01-01#, [avg_handle_minutes], NULL)", "n#,##0.0"),
    }, formats={"trips_per_member": "n#,##0.0", "rider_revenue_per_trip": 'c"$"#,##0.00',
                "avg_handle_minutes": "n#,##0.0"})
    pos_total = "{FIXED [year_month]: SUM(IIF([amount_mtd_usd] > 0, [amount_mtd_usd], 0))}"
    rv = GSource("nyc_revenue_mix", {
        "running": measure("Running total (USD)", "RUNNING_SUM(SUM([amount_mtd_usd]))", 'c"$"#,##0'),
        "neg_amount": measure("Step", "-SUM([amount_mtd_usd])"),
        "amount_signed": measure("Amount (USD)", "SUM([amount_mtd_usd])", 'c"$"#,##0'),
        "flow": dimension("Flow", 'IIF([amount_mtd_usd] >= 0, "Adds revenue", "Refunds & discounts")'),
        "nonzero": flag("Non-zero", "[amount_mtd_usd] <> 0"),
        "positive": flag("Positive", "[amount_mtd_usd] > 0"),
        "pos_share": measure("Share of revenue before tax", f"[amount_mtd_usd] / {pos_total}", pct),
    })
    wf = GSource("g_survey_waffle", {}, df=waffle())
    sr = GSource("survey_non_use_reasons", {
        "share2": measure("Share of non-users (weighted)", "SUM([weighted_share_of_non_users])", pct)})
    st = GSource("station_activity", {
        "hx": cont_dim("Hex longitude", "HEXBINX([lng] * 80, [lat] * 80) / 80", "[Geographical].[Longitude]"),
        "hy": cont_dim("Hex latitude", "HEXBINY([lng] * 80, [lat] * 80) / 80", "[Geographical].[Latitude]"),
        "casual_share": measure("Casual share of trips", "SUM([casual_trips]) / SUM([total_trips])", pct),
    })
    eb = GSource("g_ebike_long", {}, df=long_ebike(), formats={"median_min": "n#,##0.0"})

    trips_fmt = [("signed_trips", "sum", "#,##0;#,##0")]
    sheets = [
        Sheet("01 Calendar heatmap", "NYC calendar: every day vs a normal day (red = quieter, blue = busier)", w,
              rows=[("date", "my")], cols=[("date", "dom")], filters=[("city_id", "NYC")],
              layers=[Layer("Square", color=("day_vs_normal", "avg"),
                            tooltip=[("tmax_c", "max"), ("precip_mm", "max"), ("snow_mm", "max")])],
              color_scale=(("day_vs_normal", "avg"), None, DIVERGING)),
        Sheet("02 Weekday x month grid", "NYC: busiest weekday-month combinations (vs that rider type's average day)",
              w, rows=[RT, ("date", "wd")], cols=[("date", "mn")], filters=[("city_id", "NYC")],
              layers=[Layer("Square", color=("grid_index", "usr"))],
              color_scale=(("grid_index", "usr"), None, DIVERGING)),
        Sheet("03 Weather scorecard", "Weather scorecard: trips vs a normal day, by rain and snow", w,
              rows=[("condition", "dim"), RT], cols=[CITY, ("vs_normal", "usr")], filters=[("is_holiday", "False")],
              layers=[Layer("Bar", color=RT, text=("vs_normal", "usr"), labels=True)],
              formats=[("vs_normal", "usr", pct)]),
        Sheet("04 Temperature curve", "Trips vs that rider type's average day, by max temperature (2°C steps)", w,
              rows=[CITY, ("temp_index", "usr")], cols=[("temp_step", "val")], filters=[("is_holiday", "False")],
              layers=[Layer("Line", color=RT, markers=True)]),
        Sheet("05 Rain steps", "Ridership steps down as rain gets heavier (vs a normal day)", rain,
              rows=[CITY, ("rain_vs", "usr")], cols=[("rain_band", "dim")],
              layers=[Layer("Line", color=RT, text=("rain_vs", "usr"), labels=True, markers=True)],
              formats=[("rain_vs", "usr", pct)]),
        Sheet("06 Toughest days", "The toughest days: under 25% of normal trips, and the weather that day", w,
              rows=[CITY, ("date", "dim")], cols=[("day_vs_normal", "avg")], keep=["worst_day"],
              layers=[Layer("Bar", color=("day_reason", "dim"), text=("day_vs_normal", "avg"), labels=True,
                            tooltip=[("tmax_c", "max"), ("precip_mm", "max"), ("snow_mm", "max")])],
              sort=(("date", "dim"), ("day_vs_normal", "avg"), "ASC"),
              formats=[("day_vs_normal", "avg", pct)]),
        Sheet("07 Dumbbell trip length", "Average trip minutes: members vs casual riders", cc,
              rows=[CITY, ("ride_year", "dim")], cols=[[("avg_min", "avg"), ("avg_min2", "usr")]], dual="cols",
              layers=[Layer("Line", path=RT, mark_color="#bdbdbd", mark_size=1.5),
                      Layer("Circle", color=RT, text=("avg_min2", "usr"), labels=True, mark_size=1.5)]),
        Sheet("08 Diverging monthly bars", "Monthly trips: members above the line, casual riders below", cm,
              rows=[CITY, ("signed_trips", "sum")], cols=[("month_start", "month")],
              layers=[Layer("Bar", color=RT)], formats=trips_fmt),
        Sheet("09 Slope member share", "Member share of trips by ride year (Jul-Jun)", cc,
              rows=[("member_share", "avg")], cols=[("ride_year", "dim")],
              layers=[Layer("Line", color=CITY, text=("member_share", "avg"), labels=True, markers=True)],
              ),
        Sheet("10 Winter highlight table", "Winter trips as % of summer (Dec-Feb vs Jun-Aug)", se,
              rows=[CITY, RT], cols=[("ride_year", "dim")],
              layers=[Layer("Square", color=("winter_to_summer_ratio", "avg"),
                            text=("winter_to_summer_ratio", "avg"), labels=True)],
              color_scale=(("winter_to_summer_ratio", "avg"), None, SEQ_BLUE), fontsize=14, font_color=None),
        Sheet("11 Stacked area", "Monthly trips by rider type, stacked", cm,
              rows=[CITY, ("trips", "sum")], cols=[("month_start", "month")], layers=[Layer("Area", color=RT)]),
        Sheet("12 Seasonal cycle", "NYC's yearly cycle: monthly trips, one line per calendar year", cm,
              rows=[("trips", "sum")], cols=[("month_start", "mn")], filters=[("city_id", "NYC")],
              layers=[Layer("Line", color=("cal_year", "dim"), markers=True)]),
        Sheet("13 Member share by month", "Member share by calendar month (each dot = one year)", cm,
              rows=[("member_share", "avg")], cols=[("month_start", "mn")],
              layers=[Layer("Circle", color=CITY, detail=[("month_start", "yr")], mark_size=0.8)],
              formats=[("member_share", "avg", pct)]),
        Sheet("14 Price staircase", "Plan prices at each observation (USD)", ph,
              rows=[CITY, ("price_usd", "avg")], cols=[("observed_date", "day")],
              layers=[Layer("Line", color=("plan_name", "dim"), markers=True)]),
        Sheet("15 Break-even tiles", "Day passes that cost as much as one annual membership (latest prices)", pb,
              cols=[CITY], keep=["latest"],
              layers=[Layer("Text", text=("day_passes_to_break_even", "avg"),
                            tooltip=[("annual_price", "avg"), ("day_pass_price", "avg")])],
              fontsize=26),
        Sheet("16 Plan price ladder", "Plan price ladder: latest observation (USD)", ph,
              rows=[CITY, ("plan_name", "dim")], cols=[("price_usd", "avg")], keep=["latest"],
              sort=(("plan_name", "dim"), ("price_usd", "avg"), "DESC"),
              layers=[Layer("Circle", color=("plan_type", "dim"), text=("price_usd", "avg"), labels=True,
                            mark_size=1.5, tooltip=[("per_minute_usd", "avg")])]),
        Sheet("17 Revenue waterfall",
              "NYC revenue before tax, June 2026: how the total builds up (USD, preliminary)", rv,
              rows=[("running", "usr")], cols=[("category", "dim")], filters=[("year_month", "2026-06")],
              keep=["nonzero"],
              layers=[Layer("GanttBar", color=("amount_signed", "usr"), size=("neg_amount", "usr"),
                            text=("amount_mtd_usd", "sum"), labels=True)],
              color_scale=(("amount_signed", "usr"), None, ["#b2182b", "#d9d9d9", "#2a9d8f"]),
              sort=(("category", "dim"), ("amount_mtd_usd", "sum"), "DESC"),
              formats=[("running", "usr", 'c"$"#,##0'), ("amount_mtd_usd", "sum", 'c"$"#,##0')]),
        Sheet("18 Revenue mix 100%",
              "NYC revenue mix: each category's share of revenue before tax "
              "(Feb and May 2026 calculated from YTD totals)", rv,
              rows=[("pos_share", "sum")], cols=[("month_start", "month")], keep=["positive"],
              layers=[Layer("Area", color=("category", "dim"))], formats=[("pos_share", "sum", pct)]),
        Sheet("19 KPI sparklines", "NYC at a glance: members, trips per member, revenue per trip, call handling "
              "(Feb and May 2026 not published; lines join across them)",
              k, keep=["published"], rows=[[("total_annual_members", "sum"), ("trips_per_member", "avg"),
                        ("rider_revenue_per_trip", "avg"), ("handle_to_jan", "avg")]],
              cols=[("month_start", "month")], layers=[Layer("Line", mark_color="#1f4e79", markers=True)]),
        Sheet("20 Net member change", "NYC annual members: net change from the previous month", k,
              rows=[("net_change_mom", "sum")], cols=[("month_start", "month")], keep=["has_net"],
              layers=[Layer("Bar", color=("net_dir", "dim"), tooltip=[("annual_signups_or_renewals", "sum")])]),
        Sheet("21 Waffle survey", "100 cyclists: how often they use Citi Bike (2024 survey, weighted)", wf,
              rows=[("y", "sum")], cols=[("x", "sum")],
              layers=[Layer("Square", color=("group", "dim"), detail=[("cell", "dim"), ("frequency", "dim")],
                            mark_size=3)],
              ),
        Sheet("22 Lollipop reasons", "Why cyclists don't use Citi Bike (share of non-users, weighted)", sr,
              rows=[("reason", "dim")],
              cols=[[("weighted_share_of_non_users", "sum"), ("share2", "usr")]], dual="cols",
              layers=[Layer("Bar", mark_color="#9e9e9e", mark_size=0.2),
                      Layer("Circle", mark_color="#1f4e79", text=("share2", "usr"),
                            labels=True, mark_size=2)],
              sort=(("reason", "dim"), ("weighted_share_of_non_users", "sum"), "DESC")),
        Sheet("23 Hex map casual riders", "NYC: where casual riders ride (hex cells; size = trips)", st,
              rows=[("hy", "val")], cols=[("hx", "val")], filters=[("city_id", "NYC")], is_map=True,
              layers=[Layer("Circle", color=("casual_share", "usr"), size=("total_trips", "sum"))],
              color_scale=(("casual_share", "usr"), None, SEQ_ORANGE)),
        Sheet("24 E-bike vs classic", "Median trip minutes: e-bike vs classic bike (average of 4 sample months)",
              eb, rows=[CITY, RT], cols=[("median_min", "avg")],
              layers=[Layer("Circle", color=("bike", "dim"), text=("median_min", "avg"), labels=True, mark_size=1.5)]),
    ]
    sources = [w, rain, cm, cc, se, ph, pb, k, rv, wf, sr, st, eb]
    return sources, sheets


SRC = "Sources: Citi Bike, Divvy (Lyft); U.S. BTS; NOAA; NYC DOT. Jul 2023 - Jun 2026. Associations, not causes."
PAGES = [  # four charts per page, to browse the gallery
    ("Gallery 1 Weather", ["01 Calendar heatmap", "03 Weather scorecard", "05 Rain steps", "06 Toughest days"]),
    ("Gallery 2 Time", ["02 Weekday x month grid", "04 Temperature curve", "12 Seasonal cycle", "11 Stacked area"]),
    ("Gallery 3 Riders", ["07 Dumbbell trip length", "08 Diverging monthly bars", "09 Slope member share",
                          "13 Member share by month"]),
    ("Gallery 4 Price", ["14 Price staircase", "15 Break-even tiles", "16 Plan price ladder",
                         "10 Winter highlight table"]),
    ("Gallery 5 Business", ["17 Revenue waterfall", "18 Revenue mix 100%", "19 KPI sparklines",
                            "20 Net member change"]),
    ("Gallery 6 Customers", ["21 Waffle survey", "22 Lollipop reasons", "23 Hex map casual riders",
                             "24 E-bike vs classic"]),
]


def main():
    sources, sheets = build()
    if "--list" in sys.argv:
        print("\n".join([n for n, _ in PAGES] + [s.name for s in sheets]))
        return
    bw.SHEETS.update({s.name: s for s in sheets})
    dashboards = [bw.Dashboard(name, [(f"Chart gallery: {name.split(' ', 2)[2]}", "title"),
                                      ("Each chart is also its own sheet.", "body")],
                               [charts[:2], charts[2:]], [(SRC, "note")]) for name, charts in PAGES]
    cards = ("<cards><edge name='left'><strip size='160'><card type='pages' /><card type='filters' />"
             "<card type='marks' /></strip></edge><edge name='top'><strip size='2147483647'>"
             "<card type='columns' /></strip><strip size='2147483647'><card type='rows' /></strip>"
             "<strip size='31'><card type='title' /></strip></edge></cards>")
    wins = [("dashboard", d.name) for d in dashboards] + [("worksheet", s.name) for s in sheets]
    focus = wins[0][1]
    wins.sort(key=lambda x: x[1] != focus)
    pages = dict(PAGES)

    def window(cls, name):
        mx = " maximized='true'" if name == focus else ""
        if cls == "dashboard":
            vps = "".join(f"<viewpoint name={quoteattr(x)}><zoom type='entire-view' /></viewpoint>"
                          for x in pages[name])
            body = f"<viewpoints>{vps}</viewpoints><active id='-1' /><device-preview visible='false' />"
        else:
            body = cards + "<viewpoint><zoom type='entire-view' /></viewpoint>"
        return f"<window class='{cls}'{mx} name={quoteattr(name)}>{body}</window>"

    xml = ("<?xml version='1.0' encoding='utf-8' ?>\n"
           "<workbook original-version='18.1' source-build='2024.2.0 (20242.24.0716.1944)' source-platform='mac' "
           "version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>"
           f"<datasources>{''.join(s.xml() for s in sources)}</datasources>"
           "<mapsources><mapsource name='Tableau' /></mapsources>"
           f"<worksheets>{''.join(s.xml() for s in sheets)}</worksheets>"
           f"<dashboards>{''.join(d.xml() for d in dashboards)}</dashboards>"
           f"<windows source-height='30'>{''.join(window(c, n) for c, n in wins)}</windows></workbook>\n")
    shutil.rmtree(BUILD, ignore_errors=True)
    ext = BUILD / "Data" / "Extracts"
    ext.mkdir(parents=True)
    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU, parameters={"log_dir": str(BUILD)}) as hyper:
        for s in sources:
            s.write_hyper(hyper, ext)
    (BUILD / "citibike_gallery.twb").write_text(xml, encoding="utf-8")
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(BUILD / "citibike_gallery.twb", "citibike_gallery.twb")
        for h in sorted(ext.glob("*.hyper")):
            zf.write(h, f"Data/Extracts/{h.name}")
    shutil.rmtree(BUILD)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(sheets)} charts, {len(dashboards)} gallery pages, "
          f"{len(sources)} data sources")


if __name__ == "__main__":
    main()
