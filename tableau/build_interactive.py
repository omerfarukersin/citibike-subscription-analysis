"""Generate tableau/citibike_interactive.twbx: ONE interactive dashboard.

Interactivity uses Tableau parameters (drop-downs on the dashboard). Every chart has a calculated
"keep" filter that reads the parameters, so one choice updates all charts, across data sources.
Reuses the proven pieces of build_workbook.py (Hyper extracts, palette, packaging).

Run:  .venv/bin/python tableau/build_interactive.py
"""
import shutil
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from tableauhyperapi import HyperProcess, Telemetry

import build_workbook as bw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tableau" / "citibike_interactive.twbx"
BUILD = ROOT / "tableau" / "build_interactive"
DASH = "Citi Bike vs Divvy"

# ── Parameters ────────────────────────────────────────────────────────────────
PARAMS = {  # internal name -> (caption, [(value, alias)])
    "P_City": ("City", [("All", "All cities"), ("NYC", "New York (Citi Bike)"), ("CHI", "Chicago (Divvy)")]),
    "P_Rider": ("Rider type", [("All", "All riders"), ("member", "Members (subscription)"),
                               ("casual", "Casual (pay as you go)")]),
    "P_Season": ("Season", [("All", "All seasons"), ("Winter", "Winter"), ("Spring", "Spring"),
                            ("Summer", "Summer"), ("Autumn", "Autumn")]),
    "P_Year": ("Ride year (Jul-Jun)", [("All", "All 3 years"), ("2023-2024", "2023-24"),
                                        ("2024-2025", "2024-25"), ("2025-2026", "2025-26")]),
    "P_Weather": ("Weather view", [("Rain", "Rain"), ("Snow", "Snow (winter days)"),
                                   ("Temperature", "Temperature")]),
}


def p(name):
    return f"[Parameters].[{name}]"


def params_xml():
    cols = []
    for name, (cap, members) in PARAMS.items():
        first = members[0][0]
        mem = "".join(f"<member alias={quoteattr(a)} value={quoteattr(chr(34) + v + chr(34))} />" for v, a in members)
        aliases = "".join(f"<alias key={quoteattr(chr(34) + v + chr(34))} value={quoteattr(a)} />" for v, a in members)
        cols.append(f"<column caption={quoteattr(cap)} datatype='string' name='[{name}]' param-domain-type='list' "
                    f"role='measure' type='nominal' value={quoteattr(chr(34) + first + chr(34))}>"
                    f"<calculation class='tableau' formula={quoteattr(chr(34) + first + chr(34))} />"
                    f"<aliases>{aliases}</aliases>"
                    f"<members>{mem}</members></column>")
    return (f"<datasource hasconnection='false' inline='true' name='Parameters' version='18.1'>"
            f"<aliases enabled='yes' />{''.join(cols)}</datasource>")


def match(param, field):
    return f'({p(param)} = "All" OR [{field}] = {p(param)})'


# ── Data sources with calculated fields ───────────────────────────────────────
class CalcSource(bw.DataSource):
    def __init__(self, file, calcs):
        super().__init__(file)
        # calc name -> dict(caption, datatype, role, type, formula, fmt)
        self.calcs = calcs

    def xml(self):
        base = super().xml()
        defs = ""
        for name, c in self.calcs.items():
            fmt = f" default-format={quoteattr(c['fmt'])}" if c.get("fmt") else ""
            defs += (f"<column caption={quoteattr(c['caption'])} datatype='{c['datatype']}' name='[{name}]' "
                     f"role='{c['role']}' type='{c['type']}'{fmt}><calculation class='tableau' "
                     f"formula={quoteattr(c['formula'])} /></column>")
        # calculated columns must precede any <column-instance> (Tableau schema order)
        anchor = "<column-instance " if "<column-instance " in base else "<extract "
        return base.replace(anchor, defs + anchor, 1)

    def coltype(self, col):
        if col in self.calcs:
            c = self.calcs[col]
            return c["datatype"], c["role"], c["type"]
        t = self.cols[col]
        role, typ = bw.column_role(col, t)
        return t, role, typ


KINDS = dict(bw.KINDS, usr=("User", "usr", "qk", "quantitative"))


def inst(col, kind):
    _, prefix, suffix, _ = KINDS[kind]
    return f"{prefix}:{col}:{suffix}"


class Sheet:
    def __init__(self, name, title, ds, rows=(), cols=(), mark="Automatic", color=None, text=None,
                 detail=(), keep=None, filters=(), fontsize=None, uses_params=(), formats=()):
        self.__dict__.update(locals())

    def ref(self, col, kind):
        return f"[{self.ds.name}].[{inst(col, kind)}]"

    def fields(self):
        used = list(self.rows) + list(self.cols) + list(self.detail)
        used += [x for x in (self.color, self.text) if x]
        if self.keep:
            used.append((self.keep, "dim"))
        used += [(c, "dim") for c, _ in self.filters]
        out = []
        for f in used:
            if f not in out:
                out.append(f)
        return out

    def shelf(self, items):
        refs = [self.ref(c, k) for c, k in items]
        return "" if not refs else (refs[0] if len(refs) == 1 else "(" + " / ".join(refs) + ")")

    def xml(self):
        ds = self.ds
        deps, seen = [], set()
        for col, _ in self.fields():
            if col in seen:
                continue
            seen.add(col)
            t, role, typ = ds.coltype(col)
            if col in ds.calcs:
                c = ds.calcs[col]
                deps.append(f"<column caption={quoteattr(c['caption'])} datatype='{t}' name='[{col}]' role='{role}' "
                            f"type='{typ}'><calculation class='tableau' formula={quoteattr(c['formula'])} /></column>")
            else:
                deps.append(f"<column datatype='{t}' name='[{col}]' role='{role}' type='{typ}' />")
        for col, kind in self.fields():
            deriv, _, _, typ = KINDS[kind]
            deps.append(f"<column-instance column='[{col}]' derivation='{deriv}' name='[{inst(col, kind)}]' "
                        f"pivot='key' type='{typ}' />")
        pdeps = ""
        if self.uses_params:
            pcols = "".join(f"<column caption={quoteattr(PARAMS[n][0])} datatype='string' name='[{n}]' "
                            f"param-domain-type='list' role='measure' type='nominal' "
                            f"value={quoteattr(chr(34) + PARAMS[n][1][0][0] + chr(34))}>"
                            f"<calculation class='tableau' "
                            f"formula={quoteattr(chr(34) + PARAMS[n][1][0][0] + chr(34))} />"
                            f"</column>" for n in self.uses_params)
            pdeps = f"<datasource-dependencies datasource='Parameters'>{pcols}</datasource-dependencies>"
        filters, slices = "", ""
        flist = list(self.filters) + ([(self.keep, "true")] if self.keep else [])
        for col, value in flist:
            r = self.ref(col, "dim")
            member = value if value in ("true", "false") else chr(34) + value + chr(34)
            filters += (f"<filter class='categorical' column='{r}'><groupfilter function='member' "
                        f"level='[{inst(col, 'dim')}]' member={quoteattr(member)} user:ui-domain='database' "
                        f"user:ui-enumeration='inclusive' user:ui-marker='enumerate' /></filter>")
            slices += f"<column>{r}</column>"
        enc = ""
        if self.color:
            enc += f"<color column='{self.ref(*self.color)}' />"
        if self.text:
            enc += f"<text column='{self.ref(*self.text)}' />"
        for d in self.detail:
            enc += f"<lod column='{self.ref(*d)}' />"
        cell, axis = "", ""
        if self.fontsize:
            cell += (f"<format attr='font-size' value='{self.fontsize}' /><format attr='font-weight' value='bold' />"
                     f"<format attr='color' value='#1f4e79' />")
        for col, kind, fmt in self.formats:  # number formats for calculated measures (text and axis)
            cell += f"<format attr='text-format' field='{self.ref(col, kind)}' value={quoteattr(fmt)} />"
            axis += f"<format attr='text-format' field='{self.ref(col, kind)}' value={quoteattr(fmt)} />"
        rules = (f"<style-rule element='cell'>{cell}</style-rule>" if cell else "") + \
                (f"<style-rule element='axis'>{axis}</style-rule>" if axis else "")
        style = f"<style>{rules}</style>" if rules else "<style />"
        views = f"<datasource caption={quoteattr(ds.file)} name='{ds.name}' />"
        if self.uses_params:
            views = "<datasource name='Parameters' />" + views
        return (
            f"<worksheet name={quoteattr(self.name)}><layout-options><title><formatted-text>"
            f"<run fontsize='11' bold='true'>{escape(self.title)}</run></formatted-text></title></layout-options>"
            f"<table><view><datasources>{views}</datasources>{pdeps}"
            f"<datasource-dependencies datasource='{ds.name}'>{''.join(deps)}</datasource-dependencies>"
            f"{filters}{'<slices>' + slices + '</slices>' if slices else ''}<aggregation value='true' /></view>"
            f"{style}<panes><pane selection-relaxation-option='selection-relaxation-allow'>"
            f"<view><breakdown value='auto' /></view><mark class='{self.mark}' />"
            f"{'<encodings>' + enc + '</encodings>' if enc else ''}</pane></panes>"
            f"<rows>{escape(self.shelf(self.rows))}</rows><cols>{escape(self.shelf(self.cols))}</cols>"
            f"</table></worksheet>"
        )


def build():
    keep_all = " AND ".join([match("P_City", "city_id"), match("P_Rider", "rider_type"),
                             match("P_Season", "season"), match("P_Year", "ride_year")])
    keep_noseason = " AND ".join([match("P_City", "city_id"), match("P_Rider", "rider_type"),
                                  match("P_Year", "ride_year")])
    weather_cond = (f'CASE {p("P_Weather")} WHEN "Rain" THEN [rain_band] '
                    f'WHEN "Snow" THEN (IF [season] = "Winter" THEN (IF [snow_day] = "True" THEN "Snow day" '
                    f'ELSE "No snow" END) END) ELSE [temp_band] END')
    B = dict(datatype="boolean", role="dimension", type="nominal")
    daily = CalcSource("daily_weather_ridership", {
        "keep_all": dict(caption="Keep (filters)", formula=keep_all, **B),
        "keep_noseason": dict(caption="Keep (no season)", formula=keep_noseason, **B),
        "weather_condition": dict(caption="Weather condition", datatype="string", role="dimension",
                                  type="nominal", formula=weather_cond),
        "keep_weather": dict(caption="Keep (weather)", formula="[keep_all] AND NOT ISNULL([weather_condition])", **B),
        "member_trips": dict(caption="Member trips", datatype="real", role="measure", type="quantitative",
                             formula='IIF([rider_type] = "member", [trips], 0)'),
        "member_share": dict(caption="Member share", datatype="real", role="measure", type="quantitative",
                             formula="SUM([member_trips]) / SUM([trips])", fmt="p0%"),
        "rainy_vs_normal": dict(caption="Rainy days (5 mm+) vs normal", datatype="real", role="measure",
                                type="quantitative",
                                formula="AVG(IIF([precip_mm] >= 5, [trips_vs_baseline], NULL)) - 1",
                                fmt="p0%"),
        "winter_vs_summer": dict(caption="Winter trips as % of summer", datatype="real", role="measure",
                                 type="quantitative",
                                 formula='ROUND(100 * AVG(IIF([season] = "Winter", [trips], NULL)) / '
                                         'AVG(IIF([season] = "Summer", [trips], NULL)), 1)'),
    })
    price = CalcSource("price_history", {
        "keep_price": dict(caption="Keep (price)", formula=match("P_City", "city_id") +
                           ' AND [plan_name] = "Annual Membership"', **B),
    })
    kpis = CalcSource("nyc_monthly_kpis", {})
    sources = [daily, price, kpis]

    RT, CITY = ("rider_type", "dim"), ("city_id", "dim")
    sheets = [
        Sheet("KPI - trips", "Trips (selection)", daily, mark="Text", text=("trips", "sum"),
              keep="keep_all", fontsize=22, uses_params=()),
        Sheet("KPI - member share", "Member share of trips", daily, mark="Text", text=("member_share", "usr"),
              keep="keep_all", fontsize=22, formats=[("member_share", "usr", "p0%")], uses_params=()),
        Sheet("KPI - rainy days", "Rainy days (5 mm+) vs a normal day", daily, mark="Text",
              text=("rainy_vs_normal", "usr"), keep="keep_all", fontsize=22,
              formats=[("rainy_vs_normal", "usr", "p0%")], uses_params=()),
        Sheet("KPI - NYC members", "NYC annual members, Jun 2026", kpis, mark="Text",
              text=("total_annual_members", "sum"), filters=[("year_month", "2026-06")], fontsize=22),
        Sheet("Chart - monthly trips", "1  Monthly trips: members vs casual", daily,
              rows=[CITY, ("trips", "sum")], cols=[("date", "month")], mark="Line", color=RT,
              keep="keep_all", uses_params=()),
        Sheet("Chart - weather", "2  Weather: trips vs a normal day (1.0 = normal)", daily,
              rows=[CITY, ("trips_vs_baseline", "avg")], cols=[("weather_condition", "dim"), RT], mark="Bar",
              color=RT, keep="keep_weather", uses_params=()),
        Sheet("Chart - winter vs summer", "3  Winter trips as % of summer", daily,
              rows=[("winter_vs_summer", "usr")], cols=[CITY, RT], mark="Bar", color=RT,
              keep="keep_noseason", uses_params=()),
        Sheet("Chart - price", "4  Annual membership price (USD), one dot per observation", price,
              rows=[("price_usd", "avg")], cols=[("observed_date", "day")], mark="Circle", color=CITY,
              keep="keep_price", uses_params=()),
    ]
    return sources, sheets


def dashboard_xml(sheets):
    z = iter(range(2, 1000))
    W, H = 100000, 100000
    rows = [("title", 7000), ("params", 8000), ("tiles", 12500), ("charts1", 31000), ("charts2", 31000),
            ("note", 10500)]
    y, inner = 0, []
    by = {s.name: s for s in sheets}
    for kind, h in rows:
        if kind == "title":
            inner.append(f"<zone h='{h}' id='{next(z)}' type-v2='text' w='{W}' x='0' y='{y}'>" + bw.text_runs([
                ("Citi Bike vs Divvy: what drives subscription engagement?", "title"),
                ("Choose a city, rider type, season, year and weather view. Every chart updates. "
                 "Jul 2023 - Jun 2026.", "body")]) + "</zone>")
        elif kind == "params":
            w = W // len(PARAMS)
            ctrls = "".join(f"<zone h='{h}' id='{next(z)}' mode='compact' param='{p(n)}' type-v2='paramctrl' "
                            f"w='{w}' x='{i * w}' y='{y}' />" for i, n in enumerate(PARAMS))
            inner.append(f"<zone h='{h}' id='{next(z)}' param='horz' type-v2='layout-flow' w='{W}' x='0' y='{y}'>"
                         f"{ctrls}</zone>")
        elif kind == "tiles":
            names = ["KPI - trips", "KPI - member share", "KPI - rainy days", "KPI - NYC members"]
            w = W // 4
            t = "".join(f"<zone h='{h}' id='{next(z)}' name={quoteattr(n)} w='{w}' x='{i * w}' y='{y}' />"
                        for i, n in enumerate(names))
            inner.append(f"<zone h='{h}' id='{next(z)}' param='horz' type-v2='layout-flow' w='{W}' x='0' y='{y}'>"
                         f"{t}</zone>")
        elif kind.startswith("charts"):
            names = (["Chart - monthly trips", "Chart - weather"] if kind == "charts1"
                     else ["Chart - winter vs summer", "Chart - price"])
            lw = 9000
            w = (W - lw) // 2
            t = "".join(f"<zone h='{h}' id='{next(z)}' name={quoteattr(n)} w='{w}' x='{i * w}' y='{y}' />"
                        for i, n in enumerate(names))
            legend_sheet = names[0] if kind == "charts1" else names[1]
            s = by[legend_sheet]
            t += (f"<zone h='{h}' id='{next(z)}' name={quoteattr(legend_sheet)} param='{s.ref(*s.color)}' "
                  f"type-v2='color' w='{lw}' x='{W - lw}' y='{y}' />")
            inner.append(f"<zone h='{h}' id='{next(z)}' param='horz' type-v2='layout-flow' w='{W}' x='0' y='{y}'>"
                         f"{t}</zone>")
        else:
            inner.append(f"<zone h='{h}' id='{next(z)}' type-v2='text' w='{W}' x='0' y='{y}'>" + bw.text_runs([
                ("Members are the stable base: casual trips fall more in rain, snow and winter. NYC has a higher "
                 "member share (81-83% vs 64-65%) despite a pricier membership.", "head"),
                ("Weather bars compare each day with a normal day for the same city, rider type, month and weekday "
                 "type. Associations, not causes. Season does not apply to chart 3; city only to chart 4; "
                 "NYC members tile is fixed. Sources: Citi Bike, Divvy (Lyft); U.S. BTS; NOAA.", "note")]) + "</zone>")
        y += h
    return (f"<dashboard name={quoteattr(DASH)}><style /><size sizing-mode='automatic' />"
            f"<datasources /><zones>"
            f"<zone h='{H}' id='1' type-v2='layout-basic' w='{W}' x='0' y='0'>"
            f"<zone h='{H}' id='999' param='vert' type-v2='layout-flow' w='{W}' x='0' y='0'>{''.join(inner)}</zone>"
            f"</zone></zones></dashboard>")


def main():
    sources, sheets = build()
    cards = ("<cards><edge name='left'><strip size='160'><card type='pages' /><card type='filters' />"
             "<card type='marks' /></strip></edge><edge name='top'><strip size='2147483647'>"
             "<card type='columns' /></strip><strip size='2147483647'><card type='rows' /></strip>"
             "<strip size='31'><card type='title' /></strip></edge></cards>")
    vps = "".join(f"<viewpoint name={quoteattr(s.name)}><zoom type='entire-view' /></viewpoint>" for s in sheets)
    focus = DASH
    dash_win = (f"<window class='dashboard'{' maximized=' + chr(39) + 'true' + chr(39) if focus == DASH else ''} "
                f"name={quoteattr(DASH)}><viewpoints>{vps}</viewpoints>"
                f"<active id='-1' /><device-preview visible='false' /></window>")
    sheet_wins = [f"<window class='worksheet'{' maximized=' + chr(39) + 'true' + chr(39) if focus == s.name else ''} "
                  f"name={quoteattr(s.name)}>{cards}<viewpoint><zoom type='entire-view' /></viewpoint></window>"
                  for s in sheets]
    windows = dash_win + "".join(sheet_wins)
    if focus != DASH:
        windows = "".join(w for w in sheet_wins if f"name={quoteattr(focus)}" in w) + dash_win + \
                  "".join(w for w in sheet_wins if f"name={quoteattr(focus)}" not in w)
    xml = ("<?xml version='1.0' encoding='utf-8' ?>\n"
           "<workbook original-version='18.1' source-build='2024.2.0 (20242.24.0716.1944)' source-platform='mac' "
           "version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>"
           f"<datasources>{params_xml()}{''.join(s.xml() for s in sources)}</datasources>"
           f"<worksheets>{''.join(s.xml() for s in sheets)}</worksheets>"
           f"<dashboards>{dashboard_xml(sheets)}</dashboards>"
           f"<windows source-height='30'>{windows}</windows></workbook>\n")
    shutil.rmtree(BUILD, ignore_errors=True)
    ext = BUILD / "Data" / "Extracts"
    ext.mkdir(parents=True)
    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU, parameters={"log_dir": str(BUILD)}) as hyper:
        for s in sources:
            s.write_hyper(hyper, ext)
    (BUILD / "citibike_interactive.twb").write_text(xml, encoding="utf-8")
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(BUILD / "citibike_interactive.twb", "citibike_interactive.twb")
        for h in sorted(ext.glob("*.hyper")):
            zf.write(h, f"Data/Extracts/{h.name}")
    shutil.rmtree(BUILD)
    print(f"wrote {OUT.relative_to(ROOT)}: 1 dashboard, {len(sheets)} sheets, {len(PARAMS)} parameters")


if __name__ == "__main__":
    main()
