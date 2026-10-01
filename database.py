import json
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).parent
DATABASE_FILE = BASE_DIR / "maintenance.db"
SCHEMA_FILE = BASE_DIR / "schema.sql"


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_FILE)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    schema = SCHEMA_FILE.read_text(encoding="utf-8")

    with connect() as connection:
        connection.executescript(schema)


def save_readings(readings: list[dict]) -> int:
    inserted_count = 0

    with connect() as connection:
        equipment_ids = {
            reading["equipment_id"]
            for reading in readings
        }

        for equipment_id in equipment_ids:
            connection.execute(
                """
                INSERT OR IGNORE INTO equipment (
                    equipment_id,
                    name
                )
                VALUES (?, ?)
                """,
                (equipment_id, equipment_id),
            )

            connection.execute(
                """
                INSERT OR IGNORE INTO equipment_thresholds (
                    equipment_id,
                    max_temperature_c,
                    max_vibration_mm_s
                )
                VALUES (?, ?, ?)
                """,
                (equipment_id, 70.0, 4.5),
            )

        for reading in readings:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO sensor_readings (
                    equipment_id,
                    measured_at,
                    temperature_c,
                    vibration_mm_s,
                    rpm
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    reading["equipment_id"],
                    reading["timestamp"],
                    reading["temperature_c"],
                    reading["vibration_mm_s"],
                    reading["rpm"],
                ),
            )

            inserted_count += cursor.rowcount

    return inserted_count


def count_readings() -> int:
    with connect() as connection:
        result = connection.execute(
            "SELECT COUNT(*) FROM sensor_readings"
        ).fetchone()

    return result[0]

def get_equipment_summaries() -> list[dict]:
    query = """
        SELECT
            readings.equipment_id,
            COUNT(*) AS readings_count,
            ROUND(AVG(readings.temperature_c), 1) AS avg_temperature,
            MAX(readings.temperature_c) AS max_temperature,
            ROUND(AVG(readings.vibration_mm_s), 2) AS avg_vibration,
            MAX(readings.vibration_mm_s) AS max_vibration,
            thresholds.max_temperature_c,
            thresholds.max_vibration_mm_s,
            CASE
                WHEN MAX(readings.temperature_c)
                        >= thresholds.max_temperature_c
                  OR MAX(readings.vibration_mm_s)
                        >= thresholds.max_vibration_mm_s
                THEN 'attention'
                ELSE 'normal'
            END AS status
        FROM sensor_readings AS readings
        JOIN equipment_thresholds AS thresholds
          ON thresholds.equipment_id = readings.equipment_id
        GROUP BY
            readings.equipment_id,
            thresholds.max_temperature_c,
            thresholds.max_vibration_mm_s
        ORDER BY readings.equipment_id
    """

    with connect() as connection:
        rows = connection.execute(query).fetchall()

    return [dict(row) for row in rows]

def get_alert_readings() -> list[dict]:
    query = """
        SELECT
            readings.measured_at AS timestamp,
            readings.equipment_id,
            readings.temperature_c,
            readings.vibration_mm_s,
            readings.rpm,
            thresholds.max_temperature_c,
            thresholds.max_vibration_mm_s
        FROM sensor_readings AS readings
        JOIN equipment_thresholds AS thresholds
          ON thresholds.equipment_id = readings.equipment_id
        WHERE readings.temperature_c >= thresholds.max_temperature_c
           OR readings.vibration_mm_s >= thresholds.max_vibration_mm_s
        ORDER BY readings.measured_at, readings.equipment_id
    """

    with connect() as connection:
        rows = connection.execute(query).fetchall()

    return [dict(row) for row in rows]

def set_equipment_thresholds(
    equipment_id: str,
    max_temperature_c: float,
    max_vibration_mm_s: float,
) -> bool:
    with connect() as connection:
        equipment_exists = connection.execute(
            """
            SELECT 1
            FROM equipment
            WHERE equipment_id = ?
            """,
            (equipment_id,),
        ).fetchone()

        if equipment_exists is None:
            return False

        connection.execute(
            """
            INSERT INTO equipment_thresholds (
                equipment_id,
                max_temperature_c,
                max_vibration_mm_s
            )
            VALUES (?, ?, ?)
            ON CONFLICT (equipment_id) DO UPDATE SET
                max_temperature_c = excluded.max_temperature_c,
                max_vibration_mm_s = excluded.max_vibration_mm_s
            """,
            (
                equipment_id,
                max_temperature_c,
                max_vibration_mm_s,
            ),
        )

    return True

def create_maintenance_ticket_draft(
    equipment_id: str,
    source_alert_timestamp: str,
    priority: str,
    title: str,
    description: str,
    evidence: dict,
) -> tuple[dict, bool]:
    if priority not in {"medium", "high"}:
        raise ValueError("Приоритет должен быть medium или high")

    if not title.strip():
        raise ValueError("Название заявки не может быть пустым")

    if not description.strip():
        raise ValueError("Описание заявки не может быть пустым")

    with connect() as connection:
        equipment_exists = connection.execute(
            """
            SELECT 1
            FROM equipment
            WHERE equipment_id = ?
            """,
            (equipment_id,),
        ).fetchone()

        if equipment_exists is None:
            raise ValueError(
                f"Оборудование не найдено: {equipment_id}"
            )

        existing_ticket = connection.execute(
            """
            SELECT *
            FROM maintenance_tickets
            WHERE equipment_id = ?
              AND source_alert_timestamp = ?
            """,
            (
                equipment_id,
                source_alert_timestamp,
            ),
        ).fetchone()

        created = existing_ticket is None

        if created:
            cursor = connection.execute(
                """
                INSERT INTO maintenance_tickets (
                    equipment_id,
                    source_alert_timestamp,
                    priority,
                    title,
                    description,
                    evidence_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    equipment_id,
                    source_alert_timestamp,
                    priority,
                    title.strip(),
                    description.strip(),
                    json.dumps(
                        evidence,
                        ensure_ascii=False,
                    ),
                ),
            )

            ticket = connection.execute(
                """
                SELECT *
                FROM maintenance_tickets
                WHERE ticket_id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        else:
            ticket = existing_ticket

    result = dict(ticket)
    result["evidence"] = json.loads(
        result.pop("evidence_json")
    )

    return result, created


def list_maintenance_tickets() -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM maintenance_tickets
            ORDER BY created_at DESC, ticket_id DESC
            """
        ).fetchall()

    tickets = []

    for row in rows:
        ticket = dict(row)
        ticket["evidence"] = json.loads(
            ticket.pop("evidence_json")
        )
        tickets.append(ticket)

    return tickets

def approve_maintenance_ticket(
    ticket_id: int,
) -> tuple[dict, bool]:
    with connect() as connection:
        ticket = connection.execute(
            """
            SELECT *
            FROM maintenance_tickets
            WHERE ticket_id = ?
            """,
            (ticket_id,),
        ).fetchone()

        if ticket is None:
            raise ValueError(
                f"Заявка не найдена: {ticket_id}"
            )

        current_status = ticket["status"]

        if current_status == "draft":
            connection.execute(
                """
                UPDATE maintenance_tickets
                SET
                    status = 'approved',
                    updated_at = CURRENT_TIMESTAMP
                WHERE ticket_id = ?
                """,
                (ticket_id,),
            )
            changed = True

        elif current_status == "approved":
            changed = False

        else:
            raise ValueError(
                f"Нельзя одобрить заявку "
                f"со статусом {current_status}"
            )

        updated_ticket = connection.execute(
            """
            SELECT *
            FROM maintenance_tickets
            WHERE ticket_id = ?
            """,
            (ticket_id,),
        ).fetchone()

    result = dict(updated_ticket)
    result["evidence"] = json.loads(
        result.pop("evidence_json")
    )

    return result, changed
