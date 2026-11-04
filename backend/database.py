"""
DATABASE LAYER
--------------
Everything that talks to SQLite lives here. The rest of the app never
writes SQL directly - it calls these functions. This is called
"separation of concerns": if we later move to PostgreSQL / SQL Server,
only this file changes.

SQLite = a whole database stored in ONE file (ridership.db).
No server to install - perfect for small tools and pilots.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "ridership.db"

# ---------------------------------------------------------------------------
# Schema: one table. Each row = passengers at one station, one hour, one day.
# UNIQUE(...) stops the same record being counted twice if the same CSV is
# uploaded again -> we "upsert" (update if exists, else insert).
# The INDEX makes filtering by date / line fast even with millions of rows.
# ---------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS ridership (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT    NOT NULL,              -- 'YYYY-MM-DD'
    hour        INTEGER NOT NULL CHECK (hour BETWEEN 0 AND 23),
    line        TEXT    NOT NULL,
    station     TEXT    NOT NULL,
    passengers  INTEGER NOT NULL CHECK (passengers >= 0),
    UNIQUE (date, hour, line, station)
);
CREATE INDEX IF NOT EXISTS idx_ridership_date_line ON ridership (date, line);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts: row["station"]
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)


def upsert_rows(rows: list[dict]) -> int:
    """Insert rows; if (date,hour,line,station) already exists, overwrite it."""
    sql = """
        INSERT INTO ridership (date, hour, line, station, passengers)
        VALUES (:date, :hour, :line, :station, :passengers)
        ON CONFLICT (date, hour, line, station)
        DO UPDATE SET passengers = excluded.passengers
    """
    with get_connection() as conn:          # 'with' = auto COMMIT (or ROLLBACK on error)
        conn.executemany(sql, rows)         # one call for thousands of rows -> fast
    return len(rows)


def clear_all() -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM ridership")


# ---------------------------------------------------------------------------
# Filters -> WHERE clause
# We NEVER paste user input into SQL text (that allows SQL injection).
# We use ? placeholders and pass values separately.
# ---------------------------------------------------------------------------
def _where(start: str | None, end: str | None, line: str | None) -> tuple[str, list]:
    parts, params = [], []
    if start:
        parts.append("date >= ?"); params.append(start)
    if end:
        parts.append("date <= ?"); params.append(end)
    if line:
        parts.append("line = ?"); params.append(line)
    clause = ("WHERE " + " AND ".join(parts)) if parts else ""
    return clause, params


def _query(sql: str, params: list) -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_options() -> dict:
    """Values the frontend needs to build its filter dropdowns."""
    lines = _query("SELECT DISTINCT line FROM ridership ORDER BY line", [])
    rng = _query("SELECT MIN(date) AS min_date, MAX(date) AS max_date, COUNT(*) AS rows FROM ridership", [])[0]
    return {"lines": [r["line"] for r in lines], **rng}


def total_passengers(start, end, line) -> int:
    where, p = _where(start, end, line)
    return _query(f"SELECT COALESCE(SUM(passengers),0) AS t FROM ridership {where}", p)[0]["t"]


def summary(start, end, line) -> dict:
    where, p = _where(start, end, line)
    row = _query(f"""
        SELECT COALESCE(SUM(passengers),0)  AS total,
               COUNT(DISTINCT date)         AS days
        FROM ridership {where}""", p)[0]
    row["avg_daily"] = round(row["total"] / row["days"]) if row["days"] else 0
    return row


def daily(start, end, line) -> list[dict]:
    where, p = _where(start, end, line)
    return _query(f"""
        SELECT date, SUM(passengers) AS passengers
        FROM ridership {where}
        GROUP BY date ORDER BY date""", p)


def by_station(start, end, line) -> list[dict]:
    where, p = _where(start, end, line)
    return _query(f"""
        SELECT line, station, SUM(passengers) AS passengers
        FROM ridership {where}
        GROUP BY line, station ORDER BY passengers DESC""", p)


def by_hour(start, end, line) -> list[dict]:
    """Average passengers per hour per day (so long ranges don't look bigger)."""
    where, p = _where(start, end, line)
    return _query(f"""
        SELECT hour,
               ROUND(SUM(passengers) * 1.0 / COUNT(DISTINCT date)) AS avg_passengers
        FROM ridership {where}
        GROUP BY hour ORDER BY hour""", p)


def weekday_vs_weekend(start, end, line) -> list[dict]:
    """strftime('%w') gives 0=Sunday ... 6=Saturday."""
    where, p = _where(start, end, line)
    return _query(f"""
        SELECT CASE WHEN strftime('%w', date) IN ('0','6') THEN 'Weekend' ELSE 'Weekday' END AS day_type,
               ROUND(SUM(passengers) * 1.0 / COUNT(DISTINCT date)) AS avg_daily
        FROM ridership {where}
        GROUP BY day_type ORDER BY day_type DESC""", p)
