"""Generate tableau/citibike_story.twbx: the project dashboard, four tabs that tell the story.

  1 New York        who keeps Citi Bike running? (the five KPI categories)
  2 NYC vs Chicago  same company, same model: why does NYC keep more subscribers? (H3, H4)
  3 Weather         when conditions get tough, members keep riding (H1, H2)
  4 Stations        where the trips start: station maps of both cities (trip sample)

Each tab has drop-down filters (Tableau parameters, shared by all tabs) that update every chart on it.
Reuses build_gallery.py (data sources, sheets, marks) and build_interactive.py (parameters).

Run:  .venv/bin/python tableau/build_story.py
"""
import shutil
import zipfile
from pathlib import Path
from xml.sax.saxutils import quoteattr

from tableauhyperapi import HyperProcess, Telemetry

import build_workbook as bw
from build_gallery import SEQ_BLUE, GSource, Layer, Sheet, dimension, flag, long_city_comparison, measure
from build_interactive import PARAMS, match, p, params_xml

PARAMS["P_Weather"] = ("Weather view (chart 1)", [("Rain", "Rain"), ("Snow", "Snow (winter days)")])

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tableau" / "citibike_story.twbx"
BUILD = ROOT / "tableau" / "build_story"
RT, CITY = ("rider_type", "dim"), ("city_id", "dim")
PCT, NUM, USD = "p0%", "n#,##0", 'c"$"#,##0'
SRC = ("Sources: Citi Bike and Divvy (Lyft) trip data and monthly reports; U.S. Bureau of Transportation Statistics; "
       "NOAA; NYC DOT. Jul 2023 - Jun 2026. Associations, not causes.")


def ride_year(d):
    return (f'IF MONTH({d}) >= 7 THEN STR(YEAR({d})) + "-" + STR(YEAR({d}) + 1) '
            f'ELSE STR(YEAR({d}) - 1) + "-" + STR(YEAR({d})) END')


def season(d):
    return (f'CASE MONTH({d}) WHEN 12 THEN "Winter" WHEN 1 THEN "Winter" WHEN 2 THEN "Winter" '
            f'WHEN 3 THEN "Spring" WHEN 4 THEN "Spring" WHEN 5 THEN "Spring" '
            f'WHEN 6 THEN "Summer" WHEN 7 THEN "Summer" WHEN 8 THEN "Summer" ELSE "Autumn" END')


def both(*parts):
    return " AND ".join(parts)


class PSheet(Sheet):
    """A gallery sheet whose calculated fields read the dashboard parameters. The parameters are only referenced
    inside the data source's calculations: declaring them in the sheet as well makes Tableau reject charts."""


def tile(name, title, ds, field, keep, fmt, cols=()):
    return PSheet(name, title, ds, cols=list(cols), keep=keep, layers=[Layer("Text", text=field)], fontsize=20,
                  formats=[(field[0], field[1], fmt)])


def build():
    year, rider, seas, city = (match("P_Year", "ride_year"), match("P_Rider", "rider_type"),
                               match("P_Season", "season"), match("P_City", "city_id"))
    weather = (f'CASE {p("P_Weather")} WHEN "Rain" THEN [rain_band] '
               f'WHEN "Snow" THEN (IF [season] = "Winter" THEN (IF [snow_day] = "True" THEN "Snow day" '
               f'ELSE "No snow" END) END) END')
    vs_dry = ('AVG(IIF([rain_band] = "4 Heavy (20+ mm)" AND [rider_type] = "{r}", [trips_vs_baseline], NULL)) / '
              'AVG(IIF([rain_band] = "1 Dry" AND [rider_type] = "{r}", [trips_vs_baseline], NULL)) - 1')
    w = GSource("daily_weather_ridership", {
        # filters (one per use, so a chart ignores the drop-downs that do not apply to it)
        "k_nyc": flag("Keep: NYC tab", both('[city_id] = "NYC"', year, seas, rider)),
        "k_nyc_all": flag("Keep: NYC tab, all riders", both('[city_id] = "NYC"', year, seas)),
        "k_cmp": flag("Keep: comparison tab", both(year, seas, rider)),
        "k_cmp_all": flag("Keep: comparison tab, all riders", both(year, seas)),
        "k_cmp_nyc": flag("Keep: NYC share tile", both('[city_id] = "NYC"', year, seas)),
        "k_cmp_chi": flag("Keep: Chicago share tile", both('[city_id] = "CHI"', year, seas)),
        "k_wx": flag("Keep: weather tab", both(city, year, seas, rider)),
        "k_wx_all": flag("Keep: weather tab, all riders", both(city, year, seas)),
        "k_wx_year": flag("Keep: weather tab, no season", both(city, year, rider)),
        "k_wx_year_all": flag("Keep: weather tab, no season, all riders", both(city, year)),
        "weather_condition": dimension("Weather", weather),
        "k_wx_cond": flag("Keep: weather condition", "[k_wx] AND NOT ISNULL([weather_condition])"),
        # measures
        "signed_trips": measure("Trips (casual below zero)", 'IIF([rider_type] = "casual", -[trips], [trips])',
                                "n#,##0;#,##0"),
        "member_trips": measure("Member trips", 'IIF([rider_type] = "member", [trips], 0)'),
        "member_share": measure("Member share of trips", "SUM([member_trips]) / SUM([trips])", PCT),
        "avg_daily": measure("Average trips per day", "SUM([trips]) / COUNTD([date])", NUM),
        "vs_normal": measure("Trips vs a normal day", "AVG([trips_vs_baseline]) - 1", PCT),
        "base_trips": measure("Trips on a normal day", "[trips] / [trips_vs_baseline]"),
        "day_vs_normal": measure("Day vs normal (all riders)",
                                 "{FIXED [city_id], [date]: SUM([trips])} / "
                                 "{FIXED [city_id], [date]: SUM([base_trips])} - 1", PCT),
        "k_tough": flag("Keep: toughest days", "[k_wx_all] AND [day_vs_normal] < -0.75"),
        "day_reason": dimension("Weather that day",
                                'IF [snow_mm] > 0 THEN "Snow" ELSEIF [is_holiday] = "True" THEN "Holiday" '
                                'ELSEIF [precip_mm] >= 20 THEN "Heavy rain" '
                                'ELSEIF [tmax_c] < -5 THEN "Deep cold" ELSE "Day after a storm / other" END'),
        "day_label": dimension("Day",
                               '[city_id] + "  " + STR(DAY([date])) + " " + LEFT(DATENAME("month", [date]), 3) + " " '
                               '+ STR(YEAR([date])) + "  " + [day_reason]'),
        "temp_step": dict(caption="Max temperature (2°C steps)", datatype="real", role="dimension",
                          type="quantitative", formula="ROUND([tmax_c] / 2) * 2"),
        "rider_base": measure("Average day for rider type",
                              "{FIXED [city_id], [rider_type]: SUM([trips]) / COUNTD([date])}"),
        "temp_index": measure("Trips vs average day", "AVG([trips]) / AVG([rider_base])", PCT),
        "heavy_casual": measure("Casual riders, heavy rain vs dry day", vs_dry.format(r="casual"), PCT),
        "heavy_member": measure("Members, heavy rain vs dry day", vs_dry.format(r="member"), PCT),
        "snow_vs": measure("Snow day vs no-snow winter day",
                           'AVG(IIF([season] = "Winter" AND [snow_day] = "True", [trips_vs_baseline], NULL)) / '
                           'AVG(IIF([season] = "Winter" AND [snow_day] = "False", [trips_vs_baseline], NULL)) - 1',
                           PCT),
        "winter_ratio": measure("Winter trips as % of summer",
                                'AVG(IIF([season] = "Winter", [trips], NULL)) / '
                                'AVG(IIF([season] = "Summer", [trips], NULL))', PCT),
    })
    kfilter = both(match("P_Year", "ry"), match("P_Season", "season_c"))
    k = GSource("nyc_monthly_kpis", {
        "ry": dimension("Ride year (Jul-Jun)", ride_year("[month_start]")),
        "season_c": dimension("Season", season("[month_start]")),
        "k_k": flag("Keep: NYC tab", kfilter),
        "k_k_pub": flag("Keep: NYC tab, published months", kfilter + " AND NOT ISNULL([total_annual_members])"),
        "k_k_handle": flag("Keep: NYC tab, to Jan 2026", kfilter + " AND [month_start] <= #2026-01-01#"),
    }, formats={"rider_revenue_per_trip": 'c"$"#,##0.00', "avg_handle_minutes": "n#,##0.0"})
    plain = {"Ebike Surcharges & Other Fees": ("E-bike per-minute charges & other fees", "Paid per ride",
                                               "Extra per-minute charge for e-bikes, paid by members and "
                                               "casual riders"),
             "Casual Ridership": ("Single rides & day passes (casual)", "Paid per ride",
                                  "Single rides ($4.99 to unlock) and day passes ($25), bought by casual riders"),
             "Memberships": ("Annual memberships", "Paid per year", "Yearly membership fees ($239 in 2026)"),
             "Lyft Pink": ("Lyft Pink memberships", "Paid per year",
                           "Memberships bought through Lyft's own subscription (Lyft Pink, $199/year)"),
             "Sponsorship": ("Sponsorship (Citi)", "Other", "Money from the title sponsor, Citi"),
             "Overages": ("Extra-time charges", "Other", "Charges for going over the ride time limit (2023 only)"),
             "Classic Bike Refunds & Discounts": ("Refunds & discounts, classic bikes", "Refunds",
                                                  "Money given back to riders"),
             "Ebike Refunds & Discounts": ("Refunds & discounts, e-bikes", "Refunds", "Money given back to riders")}

    def case(i):
        return "CASE [category] " + " ".join(f'WHEN "{k}" THEN "{v[i]}"' for k, v in plain.items()) + " END"
    money = 'IIF(SUM([amount_mtd_usd]) < 0, "-$", "$") + STR(ROUND(ABS(SUM([amount_mtd_usd])) / 1000000, 1)) + "M"'
    rv = GSource("nyc_revenue_mix", {
        "ry": dimension("Ride year (Jul-Jun)", ride_year("[month_start]")),
        "season_c": dimension("Season", season("[month_start]")),
        "k_rv": flag("Keep: NYC tab", kfilter),
        "source": dimension("Revenue source", case(0)),
        "charge_type": dimension("Type of charge", case(1)),
        "about": dimension("What it is", case(2)),
        "rev_label": dict(caption="Amount and share", datatype="string", role="measure", type="nominal",
                          formula=f'{money} + "  (" + STR(ROUND(100 * SUM([amount_mtd_usd]) / MIN('
                                  f'{{EXCLUDE [source], [charge_type], [about]: SUM([amount_mtd_usd])}}))) + "%)"'),
        "membership_share": measure("Revenue from memberships",
                                    'SUM(IIF([category] = "Memberships" OR [category] = "Lyft Pink", '
                                    '[amount_mtd_usd], 0)) / SUM([amount_mtd_usd])', PCT),
    })
    sr = GSource("survey_non_use_reasons", {
        "share2": measure("Share of non-users (weighted)", "SUM([weighted_share_of_non_users])", PCT)})
    latest = "[observed_date] = {FIXED [city_id]: MAX([observed_date])}"
    ph = GSource("price_history", {
        "k_latest": flag("Latest observation", latest),
        "k_annual": flag("Latest annual price", latest + ' AND [plan_name] = "Annual Membership"'),
        "plan_type": dimension("Plan type", 'IIF([is_subscription] = "True", "Subscription", "Pay as you go")'),
    })
    pb = GSource("price_breakeven", {"k_latest": flag("Latest observation", latest)},
                 formats={"day_passes_to_break_even": "n#,##0.0"})
    cc = GSource("g_city_comparison_long", {
        "k_cc": flag("Keep: comparison tab", match("P_Year", "ride_year")),
        "avg_min2": measure("Average trip (minutes)", "AVG([avg_min])", "n#,##0.0"),
    }, df=long_city_comparison(), formats={"avg_min": "n#,##0.0"})
    eb = GSource("ebike_share", {
        "season_c": dimension("Season", season("DATE([year_month] + \"-01\")")),
        "k_eb": flag("Keep: comparison tab", both(match("P_Season", "season_c"), rider)),
    })

    sheets = [
        # ── Tab 1: New York ──
        tile("T1 members", "Average annual members", k, ("total_annual_members", "avg"), ["k_k"], NUM),
        tile("T1 share", "Member share of NYC trips", w, ("member_share", "usr"), ["k_nyc_all"], PCT),
        tile("T1 revenue", "Share of revenue from memberships (incl. Lyft Pink)", rv, ("membership_share", "usr"),
             ["k_rv"], PCT),
        tile("T1 signups", "Annual sign-ups or renewals", k, ("annual_signups_or_renewals", "sum"), ["k_k"], NUM),
        PSheet("N1 trips", "1  Members make most trips (members above the line, casual riders below)", w,
               rows=[("signed_trips", "sum")], cols=[("date", "month")], keep=["k_nyc"],
               layers=[Layer("Bar", color=RT)]),
        PSheet("N2 members", "2  The member base grows slowly (annual members)", k,
               rows=[("total_annual_members", "avg")], cols=[("month_start", "month")], keep=["k_k_pub"],
               layers=[Layer("Line", mark_color="#1f4e79", markers=True)]),
        PSheet("N3 signups", "3  New members sign up in spring and summer", k,
               rows=[("annual_signups_or_renewals", "sum")], cols=[("month_start", "month")], keep=["k_k"],
               layers=[Layer("Bar", mark_color="#1f4e79")]),
        PSheet("N4 revenue", "4  The money comes from ride fees, not memberships (before tax)", rv,
               rows=[("category", "dim")], cols=[("amount_mtd_usd", "sum")], keep=["k_rv"],
               sort=(("category", "dim"), ("amount_mtd_usd", "sum"), "DESC"),
               layers=[Layer("Bar", mark_color="#2a9d8f", text=("amount_mtd_usd", "sum"), labels=True)],
               formats=[("amount_mtd_usd", "sum", USD)]),
        PSheet("N5 handling", "5  Warning sign: support calls take longer (minutes, to Jan 2026)", k,
               rows=[("avg_handle_minutes", "avg")], cols=[("month_start", "month")], keep=["k_k_handle"],
               layers=[Layer("Line", mark_color="#b2182b", markers=True)]),
        PSheet("N6 reasons", "6  Why cyclists don't use Citi Bike (2024 survey; not filtered)", sr,
               rows=[("reason", "dim")],
               cols=[[("weighted_share_of_non_users", "sum"), ("share2", "usr")]], dual="cols",
               layers=[Layer("Bar", mark_color="#9e9e9e", mark_size=0.2),
                       Layer("Circle", mark_color="#1f4e79", text=("share2", "usr"), labels=True, mark_size=1.5)],
               sort=(("reason", "dim"), ("weighted_share_of_non_users", "sum"), "DESC")),
        # ── Tab 2: NYC vs Chicago ──
        tile("T2 nyc share", "NYC: member share of trips", w, ("member_share", "usr"), ["k_cmp_nyc"], PCT),
        tile("T2 chi share", "Chicago: member share of trips", w, ("member_share", "usr"), ["k_cmp_chi"], PCT),
        tile("T2 price", "Annual membership (latest price)", ph, ("price_usd", "avg"), ["k_annual"],
             'c"$"#,##0.00', cols=[CITY]),
        tile("T2 breakeven", "Day passes = 1 annual membership", pb, ("day_passes_to_break_even", "avg"),
             ["k_latest"], "n#,##0.0", cols=[CITY]),
        PSheet("C1 share", "1  NYC keeps a much higher member share, every month", w,
               rows=[("member_share", "usr")], cols=[("date", "month")], keep=["k_cmp_all"],
               layers=[Layer("Line", color=CITY, markers=True)]),
        PSheet("C2 daily", "2  Average trips per day: members vs casual riders", w,
               rows=[("avg_daily", "usr")], cols=[CITY, RT], keep=["k_cmp"],
               layers=[Layer("Bar", color=RT, text=("avg_daily", "usr"), labels=True)]),
        PSheet("C3 prices", "3  ...although NYC's membership costs more (latest prices, USD)", ph,
               rows=[CITY, ("plan_name", "dim")], cols=[("price_usd", "avg")], keep=["k_latest"],
               sort=(("plan_name", "dim"), ("price_usd", "avg"), "DESC"),
               layers=[Layer("Circle", color=("plan_type", "dim"), text=("price_usd", "avg"), labels=True,
                             mark_size=1.5)], formats=[("price_usd", "avg", 'c"$"#,##0.00')]),
        PSheet("C4 trip length", "4  Casual riders take longer trips (average minutes)", cc,
               rows=[CITY, ("ride_year", "dim")], cols=[[("avg_min", "avg"), ("avg_min2", "usr")]], dual="cols",
               keep=["k_cc"],
               layers=[Layer("Line", path=RT, mark_color="#bdbdbd", mark_size=1.5),
                       Layer("Circle", color=RT, text=("avg_min2", "usr"), labels=True, mark_size=1.5)]),
        PSheet("C5 ebikes", "5  Casual riders lean more on e-bikes (share of trips, sample months)", eb,
               rows=[("ebike_share", "avg")], cols=[CITY, RT], keep=["k_eb"],
               layers=[Layer("Bar", color=RT, text=("ebike_share", "avg"), labels=True)],
               formats=[("ebike_share", "avg", PCT)]),
        # ── Tab 3: Weather ──
        tile("T3 rain casual", "Heavy rain vs a dry day: casual riders", w, ("heavy_casual", "usr"),
             ["k_wx_all"], PCT),
        tile("T3 rain member", "Heavy rain vs a dry day: members", w, ("heavy_member", "usr"), ["k_wx_all"], PCT),
        tile("T3 snow", "Snow day vs a winter day without snow", w, ("snow_vs", "usr"), ["k_wx"], PCT),
        tile("T3 winter", "Winter trips as % of summer", w, ("winter_ratio", "usr"), ["k_wx_year"], PCT),
        PSheet("W2 condition", "1  Rain and snow hit casual riders harder (trips vs a normal day; pick Rain or "
               "Snow above)", w,
               rows=[CITY, ("vs_normal", "usr")], cols=[("weather_condition", "dim"), RT], keep=["k_wx_cond"],
               layers=[Layer("Bar", color=RT, text=("vs_normal", "usr"), labels=True)]),
        PSheet("W3 temperature", "2  Riding rises with temperature, most for casual riders", w,
               rows=[CITY, ("temp_index", "usr")], cols=[("temp_step", "val")], keep=["k_wx"],
               layers=[Layer("Line", color=RT, markers=True)]),
        PSheet("W4 winter", "3  Winter is the real test: winter trips as % of summer", w,
               rows=[CITY, RT], cols=[("ride_year", "dim")], keep=["k_wx_year"],
               layers=[Layer("Square", color=("winter_ratio", "usr"), text=("winter_ratio", "usr"), labels=True)],
               color_scale=(("winter_ratio", "usr"), None, SEQ_BLUE), fontsize=13, font_color=None),
    ]
    trips_sel = (f'CASE {p("P_Rider")} WHEN "member" THEN [member_trips] WHEN "casual" THEN [casual_trips] '
                 f'ELSE [total_trips] END')
    st = GSource("station_activity", {
        "trips_sel": measure("Trips (rider type chosen above)", trips_sel, NUM),
        "mshare": measure("Member share of trips", "SUM([member_trips]) / SUM([total_trips])", PCT),
        "k_nyc_st": flag("NYC stations", '[city_id] = "NYC"'),
        "k_chi_st": flag("Chicago stations", '[city_id] = "CHI"'),
    })
    member_scale = ["#e8833a", "#f7f7f7", "#1f4e79"]  # orange = mostly casual, blue = mostly members
    for city, name, keep in [("NYC", "New York", "k_nyc_st"), ("Chicago", "Chicago", "k_chi_st")]:
        sheets += [
            tile(f"T4 {city} stations", f"{name}: stations", st, ("station_key", "cntd"), [keep], NUM),
            tile(f"T4 {city} trips", f"{name}: trips in the sample months", st, ("trips_sel", "sum"), [keep], NUM),
            PSheet(f"M {city}", f"{'1' if city == 'NYC' else '2'}  {name}: each station, size = trips, "
                   f"colour = member share (blue = mostly members, orange = mostly casual)", st,
                   rows=[("lat", "avg")], cols=[("lng", "avg")], keep=[keep], is_map=True,
                   layers=[Layer("Circle", color=("mshare", "usr"), size=("trips_sel", "sum"),
                                 detail=[("station_key", "dim"), ("station_name", "dim")])],
                   color_scale=(("mshare", "usr"), None, member_scale)),
        ]
    return [w, k, rv, sr, ph, pb, cc, eb, st], sheets


# ── Dashboards ────────────────────────────────────────────────────────────────
TABS = [
    ("1 New York", "New York: members are the core of Citi Bike",
     "Who keeps Citi Bike running? The five KPI areas: engagement (1), retention (2), acquisition (3), "
     "monetization (4) and satisfaction (5, 6).",
     ["P_Year", "P_Season", "P_Rider"],
     ["T1 members", "T1 share", "T1 revenue", "T1 signups"],
     [(["N1 trips", "N2 members", "N3 signups"], "N1 trips"), (["N4 revenue", "N5 handling", "N6 reasons"], None)],
     [("So what: members make about 4 in 5 NYC trips but bring in under a quarter of the revenue; most money "
       "comes from per-ride charges, above all e-bike minutes. New members arrive in spring and summer, the moment "
       "to recruit new riders, and longer call-handling times are a warning sign.", "head"),
      ("Trips from BTS (NYC only). Members, sign-ups and revenue from Citi Bike's monthly reports; Feb and May 2026 "
       "not published (members blank; revenue calculated from year-to-date totals). Call handling shown to "
       "Jan 2026; later reports: 17.3 (Mar), 14.4 (Apr), 10.9 (Jun) min. Revenue is before tax (sales tax "
       "collected for the government is left out), preliminary and unaudited. " + SRC, "note")]),
    ("2 NYC vs Chicago", "NYC keeps more subscribers than Chicago, despite a pricier membership",
     "H3: member share differs between the cities (supported; price alone does not explain it). "
     "H4: e-bike use differs by rider type (supported).",
     ["P_Year", "P_Season", "P_Rider"],
     ["T2 nyc share", "T2 chi share", "T2 price", "T2 breakeven"],
     [(["C1 share", "C2 daily"], "C1 share"), (["C3 prices", "C4 trip length", "C5 ebikes"], "C4 trip length")],
     [("So what: the difference is linked to how single rides are priced, not only to the membership price. "
       "NYC charges a flat $4.49-$4.99 per ride; Chicago charges $1 plus a per-minute rate, so short casual rides "
       "are cheaper there and subscribing pays off less. City size, commuting and tourism also differ.", "head"),
      ("Member share from BTS (NYC) and Divvy trip files (Chicago). Prices are snapshots from official pages. E-bike "
       "shares from the trip sample (Jul 2025, Oct 2025, Jan 2026, Apr 2026); Season picks the sample month. " + SRC,
       "note")]),
    ("3 Weather", "When conditions get tough, members keep riding",
     "H1: casual riders are more weather-sensitive than members (supported). "
     "H2: the winter drop is deeper in Chicago, and members hold up better (supported).",
     ["P_City", "P_Year", "P_Season", "P_Rider", "P_Weather"],
     ["T3 rain casual", "T3 rain member", "T3 snow", "T3 winter"],
     [(["W2 condition", "W3 temperature", "W4 winter"], "W2 condition", 66000)],
     [("So what: members are the reliable base in bad weather and in winter. Casual trips fall further in heavy rain "
       "and snow, and Chicago's casual riding drops to about 10-13% of its summer level in winter.", "head"),
      ("Each day is compared with a normal day for the same city, rider type, month and weekday type. Weather from "
       "NOAA (Central Park, O'Hare). Tiles 1-2 ignore the Rider filter; tile 4 and chart 3 ignore Season. " + SRC,
       "note")]),
    ("4 Stations", "Where people ride: busy centres are member territory, parks and edges draw casual riders",
     "Every station in New York and Chicago. Pick a rider type to size the circles by member or casual trips.",
     ["P_Rider"],
     ["T4 NYC stations", "T4 NYC trips", "T4 Chicago stations", "T4 Chicago trips"],
     [(["M NYC", "M Chicago"], "M NYC", 66000)],
     [("So what: members ride across the dense core of each city, where commuting trips start and end; casual riding "
       "concentrates around parks, waterfronts and tourist areas. NYC's network is about twice the size of Chicago's "
       "and carries about ten times the trips in the sample months.", "head"),
      ("Station activity from the trip files for four sample months (Jul 2025, Oct 2025, Jan 2026, Apr 2026), so the "
       "Year and Season filters do not apply. Stations with fewer than 10 trips are left out. " + SRC, "note")]),
]



W_PX, H_PX = 1400, 880  # fixed page size: fits a laptop screen and Tableau Public


def dashboard_xml(name, title, subtitle, params, tiles, rows, notes, by):
    z = iter(range(2, 2000))
    W = 100000
    rows = [r if len(r) == 3 else (*r, 30000) for r in rows]
    layout = [("title", 6000), ("params", 5000), ("tiles", 9000)] + [("row", r[2]) for r in rows] + [("note", 9000)]
    scale = 100000 / sum(h for _, h in layout)
    y, inner, row_i = 0, [], 0
    for kind, h in layout:
        h = int(h * scale)
        if kind == "title":
            inner.append(f"<zone h='{h}' id='{next(z)}' type-v2='text' w='{W}' x='0' y='{y}'>"
                         + bw.text_runs([(title, "title"), (subtitle, "body")]) + "</zone>")
        elif kind == "params":
            w = W // max(len(params), 5)
            ctrls = "".join(f"<zone h='{h}' id='{next(z)}' mode='compact' param='{p(n)}' type-v2='paramctrl' "
                            f"w='{w}' x='{i * w}' y='{y}' />" for i, n in enumerate(params))
            inner.append(f"<zone h='{h}' id='{next(z)}' param='horz' type-v2='layout-flow' w='{W}' x='0' y='{y}'>"
                         f"{ctrls}</zone>")
        elif kind == "tiles":
            w = W // len(tiles)
            t = "".join(f"<zone h='{h}' id='{next(z)}' name={quoteattr(n)} w='{w}' x='{i * w}' y='{y}' />"
                        for i, n in enumerate(tiles))
            inner.append(f"<zone h='{h}' id='{next(z)}' param='horz' type-v2='layout-flow' w='{W}' x='0' y='{y}'>"
                         f"{t}</zone>")
        elif kind == "row":
            names, legend, _ = rows[row_i]
            row_i += 1
            lw = 8500 if legend else 0
            w = (W - lw) // len(names)
            t = "".join(f"<zone h='{h}' id='{next(z)}' name={quoteattr(n)} w='{w}' x='{i * w}' y='{y}' />"
                        for i, n in enumerate(names))
            if legend:
                s = by[legend]
                field = s.color_scale[0] if s.color_scale else s.color
                t += (f"<zone h='{h}' id='{next(z)}' name={quoteattr(legend)} param='{s.ref(*field)}' "
                      f"type-v2='color' w='{lw}' x='{W - lw}' y='{y}' />")
            inner.append(f"<zone h='{h}' id='{next(z)}' param='horz' type-v2='layout-flow' w='{W}' x='0' y='{y}'>"
                         f"{t}</zone>")
        else:
            inner.append(f"<zone h='{h}' id='{next(z)}' type-v2='text' w='{W}' x='0' y='{y}'>"
                         + bw.text_runs(notes) + "</zone>")
        y += h
    return (f"<dashboard name={quoteattr(name)}><style /><size maxheight='{H_PX}' maxwidth='{W_PX}' "
            f"minheight='{H_PX}' minwidth='{W_PX}' sizing-mode='fixed' /><datasources /><zones>"
            f"<zone h='100000' id='1' type-v2='layout-basic' w='{W}' x='0' y='0'>"
            f"<zone h='100000' id='1999' param='vert' type-v2='layout-flow' w='{W}' x='0' y='0'>{''.join(inner)}"
            f"</zone></zone></zones></dashboard>")


def main():
    sources, sheets = build()
    tabs = TABS
    keep = {n for t in tabs for n in t[4] + [x for r in t[5] for x in r[0]]}
    sheets = [s for s in sheets if s.name in keep]
    by = {s.name: s for s in sheets}
    dashboards = [dashboard_xml(*t, by) for t in tabs]
    cards = ("<cards><edge name='left'><strip size='160'><card type='pages' /><card type='filters' />"
             "<card type='marks' /></strip></edge><edge name='top'><strip size='2147483647'>"
             "<card type='columns' /></strip><strip size='2147483647'><card type='rows' /></strip>"
             "<strip size='31'><card type='title' /></strip></edge></cards>")
    focus = tabs[0][0]  # the workbook opens on the first tab
    tab_sheets = {t[0]: t[4] + [n for r in t[5] for n in r[0]] for t in tabs}

    def dash_window(name):
        vps = "".join(f"<viewpoint name={quoteattr(x)}><zoom type='entire-view' /></viewpoint>"
                      for x in tab_sheets[name])
        mx = " maximized='true'" if name == focus else ""
        return (f"<window class='dashboard'{mx} name={quoteattr(name)}><viewpoints>{vps}</viewpoints>"
                f"<active id='-1' /><device-preview visible='false' /></window>")

    wins = [dash_window(t[0]) for t in tabs]
    wins.sort(key=lambda x: f"name={quoteattr(focus)}" not in x)
    wins += [f"<window class='worksheet' hidden='true' name={quoteattr(s.name)}>{cards}"
             f"<viewpoint><zoom type='entire-view' /></viewpoint></window>" for s in sheets]
    xml = ("<?xml version='1.0' encoding='utf-8' ?>\n"
           "<workbook original-version='18.1' source-build='2024.2.0 (20242.24.0716.1944)' source-platform='mac' "
           "version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>"
           f"<datasources>{params_xml()}{''.join(s.xml() for s in sources)}</datasources>"
           "<mapsources><mapsource name='Tableau' /></mapsources>"
           f"<worksheets>{''.join(s.xml() for s in sheets)}</worksheets>"
           f"<dashboards>{''.join(dashboards)}</dashboards>"
           f"<windows source-height='30'>{''.join(wins)}</windows></workbook>\n")
    shutil.rmtree(BUILD, ignore_errors=True)
    ext = BUILD / "Data" / "Extracts"
    ext.mkdir(parents=True)
    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU, parameters={"log_dir": str(BUILD)}) as hyper:
        for s in sources:
            s.write_hyper(hyper, ext)
    (BUILD / "citibike_story.twb").write_text(xml, encoding="utf-8")
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(BUILD / "citibike_story.twb", "citibike_story.twb")
        for h in sorted(ext.glob("*.hyper")):
            zf.write(h, f"Data/Extracts/{h.name}")
    shutil.rmtree(BUILD)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(tabs)} dashboards, {len(sheets)} sheets, {len(PARAMS)} filters")


if __name__ == "__main__":
    main()
