"""
CSV VALIDATION
--------------
Real-world data from station staff / ticket machines is often messy:
missing values, typos, impossible numbers. Rule #1 of data work:
never trust input. We check every row, keep the good ones, and report
exactly which rows were rejected and WHY - so the person who sent the
file can fix it at the source.
"""
import csv
import io
from datetime import date

REQUIRED_COLUMNS = {"date", "hour", "line", "station", "passengers"}


class CSVFormatError(Exception):
    """Raised when the file as a whole is unusable (wrong columns, not CSV...)."""


def parse_csv(raw_bytes: bytes) -> tuple[list[dict], list[dict]]:
    """Returns (valid_rows, errors). errors = [{'row': 3, 'reason': '...'}]"""
    try:
        text = raw_bytes.decode("utf-8-sig")  # utf-8-sig also strips Excel's BOM
    except UnicodeDecodeError:
        raise CSVFormatError("File is not UTF-8 text. Save it as 'CSV UTF-8' in Excel.")

    reader = csv.DictReader(io.StringIO(text))
    headers = {h.strip().lower() for h in (reader.fieldnames or [])}
    missing = REQUIRED_COLUMNS - headers
    if missing:
        raise CSVFormatError(f"Missing column(s): {', '.join(sorted(missing))}")

    valid, errors = [], []
    # start=2 because row 1 is the header -> numbers match what you see in Excel
    for line_no, raw in enumerate(reader, start=2):
        row = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        try:
            valid.append(_validate(row))
        except ValueError as e:
            errors.append({"row": line_no, "reason": str(e)})
    return valid, errors


def _validate(row: dict) -> dict:
    try:
        d = date.fromisoformat(row["date"])
    except ValueError:
        raise ValueError(f"bad date '{row['date']}' (use YYYY-MM-DD)")

    if not row["hour"].isdigit() or not 0 <= int(row["hour"]) <= 23:
        raise ValueError(f"hour must be 0-23, got '{row['hour']}'")

    if not row["line"]:
        raise ValueError("line is empty")
    if not row["station"]:
        raise ValueError("station is empty")

    if not row["passengers"].lstrip("-").isdigit():
        raise ValueError(f"passengers must be a whole number, got '{row['passengers']}'")
    if int(row["passengers"]) < 0:
        raise ValueError("passengers cannot be negative")

    return {
        "date": d.isoformat(),
        "hour": int(row["hour"]),
        "line": row["line"],
        "station": row["station"],
        "passengers": int(row["passengers"]),
    }
