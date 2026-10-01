from contextlib import asynccontextmanager

from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, File, HTTPException, UploadFile

from database import (
    get_alert_readings,
    get_equipment_summaries,
    initialize_database,
    count_readings,
    save_readings,
    list_maintenance_tickets,
)
from main import find_alerts, load_readings
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from ai_service import AIReportUnavailable, generate_maintenance_report


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Maintenance Copilot API",
    description="API для анализа показаний промышленного оборудования",
    version="0.1.0",
    lifespan=lifespan,
)

MAX_UPLOAD_SIZE = 2 * 1024 * 1024
STATIC_DIR = Path(__file__).parent / "static"

@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "maintenance-copilot",
    }


@app.get("/api/report")
def report() -> dict:
    equipment = get_equipment_summaries()
    alert_readings = get_alert_readings()
    alerts = find_alerts(alert_readings)
    tickets = list_maintenance_tickets()

    return {
        "equipment": equipment,
        "alerts": alerts,
        "equipment_count": len(equipment),
        "alerts_count": len(alerts),
        "tickets": tickets,
        "tickets_count": len(tickets),
    }

@app.post("/api/readings/import")
async def import_readings(
    file: UploadFile = File(...),
) -> dict:
    filename = file.filename or ""

    if Path(filename).suffix.lower() != ".csv":
        raise HTTPException(
            status_code=400,
            detail="Разрешены только CSV-файлы",
        )

    content = await file.read(MAX_UPLOAD_SIZE + 1)
    await file.close()

    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Размер CSV не должен превышать 2 МБ",
        )

    temporary_path = None

    try:
        with NamedTemporaryFile(
            suffix=".csv",
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_path = Path(temporary_file.name)

        readings = load_readings(temporary_path)
        inserted_count = save_readings(readings)

    except (ValueError, UnicodeDecodeError) as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return {
        "filename": filename,
        "readings_in_file": len(readings),
        "inserted_count": inserted_count,
        "total_readings": count_readings(),
    }

@app.post("/api/ai-report")
def create_ai_report() -> dict:
    equipment = get_equipment_summaries()

    if not equipment:
        raise HTTPException(
            status_code=400,
            detail="В базе нет измерений",
        )

    alert_readings = get_alert_readings()
    alerts = find_alerts(alert_readings)

    try:
        return generate_maintenance_report(
            equipment,
            alerts,
        )

    except AIReportUnavailable as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)
