"""
INSIGHTS + AUTOMATED EXCEL REPORT
---------------------------------
This is the "DX" part. Before: someone copies numbers into Excel every
week by hand (~1-2 hours). After: one click produces the same report,
plus plain-language findings a manager can read in 30 seconds.

Insights are simple rules (no AI needed). Later, an LLM could turn these
same numbers into a written summary - but rules first: they are
predictable, explainable, and free.
"""
import io
from datetime import date, timedelta

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Font, PatternFill

from . import database as db


def build_dashboard(start, end, line) -> dict:
    """Everything the dashboard needs, in one response."""
    s = db.summary(start, end, line)
    stations = db.by_station(start, end, line)
    hours = db.by_hour(start, end, line)
    week = db.weekday_vs_weekend(start, end, line)
    days = db.daily(start, end, line)

    s["busiest_station"] = stations[0]["station"] if stations else None
    peak = max(hours, key=lambda h: h["avg_passengers"]) if hours else None
    s["peak_hour"] = peak["hour"] if peak else None
    s["change_pct"] = _change_vs_previous(start, end, line, s["total"])

    return {
        "summary": s,
        "daily": days,
        "stations": stations,
        "hours": hours,
        "week": week,
        "insights": _insights(s, stations, hours, week, days),
    }


def _change_vs_previous(start, end, line, current_total):
    """Compare with the same number of days just before 'start'."""
    if not (start and end):
        return None
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    length = (e - s).days + 1
    prev_end = s - timedelta(days=1)
    prev_start = prev_end - timedelta(days=length - 1)
    prev = db.total_passengers(prev_start.isoformat(), prev_end.isoformat(), line)
    if prev == 0:
        return None
    return round((current_total - prev) / prev * 100, 1)


def _insights(s, stations, hours, week, days) -> list[str]:
    out = []
    if not s["total"]:
        return ["No data for this selection. Upload a CSV or widen the date range."]

    if stations:
        top = stations[0]
        share = top["passengers"] / s["total"] * 100
        out.append(f"{top['station']} ({top['line']}) is the busiest stop with "
                   f"{share:.0f}% of all passengers.")
        low = stations[-1]
        out.append(f"{low['station']} is the quietest stop - a candidate for "
                   f"reduced frequency or targeted promotion.")

    if s.get("peak_hour") is not None:
        out.append(f"Peak hour is {s['peak_hour']:02d}:00. Extra staff or "
                   f"vehicles are most useful around this time.")

    w = {r["day_type"]: r["avg_daily"] for r in week}
    if w.get("Weekday") and w.get("Weekend"):
        diff = (w["Weekend"] - w["Weekday"]) / w["Weekday"] * 100
        word = "higher" if diff >= 0 else "lower"
        out.append(f"Weekend ridership is {abs(diff):.0f}% {word} than weekdays "
                   f"(tourist demand).")

    if days:
        best = max(days, key=lambda d: d["passengers"])
        out.append(f"Busiest single day: {best['date']} with {best['passengers']:,} passengers.")

    if s.get("change_pct") is not None:
        word = "up" if s["change_pct"] >= 0 else "down"
        out.append(f"Total ridership is {word} {abs(s['change_pct'])}% vs the previous "
                   f"period of the same length.")
    return out


def build_excel(start, end, line) -> bytes:
    """Create a 3-sheet Excel report in memory and return its bytes."""
    data = build_dashboard(start, end, line)
    wb = Workbook()
    bold = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="1F4E79")

    def header(ws, cols):
        ws.append(cols)
        for c in ws[ws.max_row]:
            c.font, c.fill = bold, fill

    # Sheet 1: Summary + insights
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Ridership Report"]); ws["A1"].font = Font(bold=True, size=14)
    ws.append(["Period", f"{start or 'all'} to {end or 'all'}"])
    ws.append(["Line", line or "All lines"])
    ws.append([])
    s = data["summary"]
    for label, val in [("Total passengers", s["total"]), ("Days", s["days"]),
                       ("Average per day", s["avg_daily"]),
                       ("Busiest station", s["busiest_station"]),
                       ("Peak hour", f"{s['peak_hour']:02d}:00" if s["peak_hour"] is not None else "-"),
                       ("Change vs previous period (%)", s["change_pct"])]:
        ws.append([label, val])
    ws.append([])
    ws.append(["Key findings"]); ws.cell(ws.max_row, 1).font = Font(bold=True)
    for i in data["insights"]:
        ws.append(["•", i])
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 90

    # Sheet 2: Daily trend + line chart
    ws2 = wb.create_sheet("Daily")
    header(ws2, ["Date", "Passengers"])
    for r in data["daily"]:
        ws2.append([r["date"], r["passengers"]])
    ws2.column_dimensions["A"].width = 14
    if data["daily"]:
        ch = LineChart(); ch.title = "Daily passengers"; ch.height, ch.width = 8, 22
        ch.add_data(Reference(ws2, min_col=2, min_row=1, max_row=ws2.max_row), titles_from_data=True)
        ch.set_categories(Reference(ws2, min_col=1, min_row=2, max_row=ws2.max_row))
        ws2.add_chart(ch, "D2")

    # Sheet 3: Stations + bar chart
    ws3 = wb.create_sheet("Stations")
    header(ws3, ["Line", "Station", "Passengers"])
    for r in data["stations"]:
        ws3.append([r["line"], r["station"], r["passengers"]])
    ws3.column_dimensions["A"].width = 18; ws3.column_dimensions["B"].width = 26
    if data["stations"]:
        ch = BarChart(); ch.title = "Passengers by station"; ch.height, ch.width = 8, 18
        ch.add_data(Reference(ws3, min_col=3, min_row=1, max_row=ws3.max_row), titles_from_data=True)
        ch.set_categories(Reference(ws3, min_col=2, min_row=2, max_row=ws3.max_row))
        ws3.add_chart(ch, "E2")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
