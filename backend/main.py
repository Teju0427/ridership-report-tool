"""
BACKEND API (FastAPI)
---------------------
The API is the "waiter" between the frontend (browser) and the database.
The browser sends HTTP requests -> FastAPI runs a Python function ->
returns JSON (or a file).

Endpoints
  GET    /api/options           filter values (lines, date range)
  POST   /api/upload            upload a CSV file
  GET    /api/dashboard         KPIs + chart data + insights
  GET    /api/report.xlsx       download Excel report
  DELETE /api/data              wipe all data (demo reset)
  GET    /                      serves the frontend (index.html)

Run:   uvicorn backend.main:app --reload
Docs:  http://127.0.0.1:8000/docs   (auto-generated, try endpoints there!)
"""
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from . import csv_loader
from . import database as db
from . import report

MAX_UPLOAD_MB = 10
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()  # runs once at startup: creates the table if it doesn't exist
    yield         # app runs here; code after yield would run at shutdown


app = FastAPI(title="Ridership Report Tool", version="1.0", lifespan=lifespan)


def _check_dates(start: str | None, end: str | None):
    """Validate query params so bad input gives a clear 400 error, not a crash."""
    for name, val in (("start", start), ("end", end)):
        if val:
            try:
                date.fromisoformat(val)
            except ValueError:
                raise HTTPException(400, f"'{name}' must be YYYY-MM-DD")
    if start and end and start > end:
        raise HTTPException(400, "'start' must be before 'end'")


@app.get("/api/options")
def options():
    return db.get_options()


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a .csv file")
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File too large (max {MAX_UPLOAD_MB} MB)")

    try:
        valid, errors = csv_loader.parse_csv(raw)
    except csv_loader.CSVFormatError as e:
        raise HTTPException(400, str(e))

    saved = db.upsert_rows(valid) if valid else 0
    return {
        "filename": file.filename,
        "saved_rows": saved,
        "rejected_rows": len(errors),
        "errors": errors[:20],  # show first 20 so the response stays small
    }


@app.get("/api/dashboard")
def dashboard(start: str | None = Query(None), end: str | None = Query(None),
              line: str | None = Query(None)):
    _check_dates(start, end)
    return report.build_dashboard(start, end, line or None)


@app.get("/api/report.xlsx")
def download_report(start: str | None = None, end: str | None = None,
                    line: str | None = None):
    _check_dates(start, end)
    content = report.build_excel(start, end, line or None)
    name = f"ridership_report_{start or 'all'}_{end or 'all'}.xlsx"
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@app.delete("/api/data")
def delete_all():
    db.clear_all()
    return {"ok": True}


# Serve index.html, style.css, app.js from /frontend at "/".
# Mounted LAST so it doesn't swallow the /api routes above.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
