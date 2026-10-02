import argparse
import json
from pathlib import Path

from database import (
    approve_maintenance_ticket,
    create_maintenance_ticket_draft,
    get_alert_readings,
    get_equipment_summaries,
    get_equipment_profile,
    initialize_database,
    list_manual_documents,
    list_maintenance_tickets,
    set_equipment_profile,
)
from knowledge_service import (
    ManualKnowledgeUnavailable,
    index_manual,
    search_manual,
)
from main import find_alerts


def get_equipment_snapshot(equipment_id: str) -> dict:
    summaries = get_equipment_summaries()

    summary = next(
        (
            item
            for item in summaries
            if item["equipment_id"] == equipment_id
        ),
        None,
    )

    if summary is None:
        raise ValueError(
            f"Оборудование не найдено: {equipment_id}"
        )

    alert_readings = [
        reading
        for reading in get_alert_readings()
        if reading["equipment_id"] == equipment_id
    ]

    alerts = find_alerts(alert_readings)

    return {
        "equipment_id": equipment_id,
        "profile": get_equipment_profile(equipment_id),
        "status": summary["status"],
        "thresholds": {
            "max_temperature_c": summary["max_temperature_c"],
            "max_vibration_mm_s": summary["max_vibration_mm_s"],
        },
        "summary": {
            "readings_count": summary["readings_count"],
            "avg_temperature_c": summary["avg_temperature"],
            "max_temperature_c": summary["max_temperature"],
            "avg_vibration_mm_s": summary["avg_vibration"],
            "max_vibration_mm_s": summary["max_vibration"],
        },
        "latest_alerts": alerts[-5:],
    }


def create_ticket_draft(equipment_id: str) -> dict:
    snapshot = get_equipment_snapshot(equipment_id)

    if snapshot["status"] != "attention":
        raise ValueError(
            f"Для {equipment_id} нет текущего превышения порогов"
        )

    if not snapshot["latest_alerts"]:
        raise ValueError(
            f"Для {equipment_id} не найдено предупреждений"
        )

    latest_alert = snapshot["latest_alerts"][-1]
    reasons = latest_alert["reasons"]

    priority = (
        "high"
        if len(reasons) >= 2
        else "medium"
    )

    title = (
        f"Проверить {equipment_id}: "
        "превышение контрольных порогов"
    )

    description = (
        f"Зафиксировано предупреждение "
        f"{latest_alert['timestamp']}: "
        f"{'; '.join(reasons)}. "
        "Требуется проверка специалистом "
        "по действующему регламенту."
    )

    evidence = {
        "thresholds": snapshot["thresholds"],
        "summary": snapshot["summary"],
        "alert": latest_alert,
    }

    ticket, created = create_maintenance_ticket_draft(
        equipment_id=equipment_id,
        source_alert_timestamp=latest_alert["timestamp"],
        priority=priority,
        title=title,
        description=description,
        evidence=evidence,
    )

    return {
        "created": created,
        "ticket": ticket,
    }


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Инструменты EnlikHelper для AI-агента"
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    snapshot_command = commands.add_parser(
        "snapshot",
        help="Получить снимок состояния оборудования",
    )
    snapshot_command.add_argument(
        "equipment_id",
        help="Идентификатор оборудования",
    )

    ticket_command = commands.add_parser(
        "create-ticket-draft",
        help="Создать черновик заявки на обслуживание",
    )
    ticket_command.add_argument(
        "equipment_id",
        help="Идентификатор оборудования",
    )
    approve_command = commands.add_parser(
        "approve-ticket",
        help="Одобрить черновик заявки",
    )
    approve_command.add_argument(
        "ticket_id",
        type=int,
        help="Номер заявки",
    )
    commands.add_parser(
        "list-tickets",
        help="Показать заявки на обслуживание",
    )

    profile_command = commands.add_parser(
        "set-profile",
        help="Сохранить паспортный профиль оборудования",
    )
    profile_command.add_argument("equipment_id")
    profile_command.add_argument("--manufacturer", default=None)
    profile_command.add_argument("--model", default=None)
    profile_command.add_argument("--serial", dest="serial_number", default=None)

    index_manual_command = commands.add_parser(
        "index-manual",
        help="Проиндексировать PDF-инструкцию",
    )
    index_manual_command.add_argument(
        "equipment_id",
        help="Идентификатор оборудования",
    )
    index_manual_command.add_argument(
        "file",
        type=Path,
        help="Путь к PDF-файлу",
    )

    search_manual_command = commands.add_parser(
        "search-manual",
        help="Найти фрагменты в инструкции",
    )
    search_manual_command.add_argument(
        "equipment_id",
        help="Идентификатор оборудования",
    )
    search_manual_command.add_argument(
        "query",
        help="Поисковый запрос",
    )

    list_manuals_command = commands.add_parser(
        "list-manuals",
        help="Показать загруженные инструкции",
    )
    list_manuals_command.add_argument(
        "equipment_id",
        nargs="?",
        help="Необязательный идентификатор оборудования",
    )

    return parser


def main() -> None:
    initialize_database()
    parser = create_parser()
    arguments = parser.parse_args()

    try:
        if arguments.command == "snapshot":
            result = get_equipment_snapshot(
                arguments.equipment_id
            )

        elif arguments.command == "create-ticket-draft":
            result = create_ticket_draft(
                arguments.equipment_id
            )
        elif arguments.command == "approve-ticket":
            ticket, changed = approve_maintenance_ticket(
                arguments.ticket_id
            )
            result = {
                "approved": changed,
                "ticket": ticket,
            }
        elif arguments.command == "list-tickets":
            result = {
                "tickets": list_maintenance_tickets()
            }

        elif arguments.command == "set-profile":
            result = set_equipment_profile(
                equipment_id=arguments.equipment_id,
                manufacturer=arguments.manufacturer,
                model=arguments.model,
                serial_number=arguments.serial_number,
            )

        elif arguments.command == "index-manual":
            if arguments.file.suffix.lower() != ".pdf":
                raise ValueError("Инструкция должна быть PDF-файлом")

            if not arguments.file.is_file():
                raise ValueError(
                    f"Файл не найден: {arguments.file}"
                )

            result = index_manual(
                equipment_id=arguments.equipment_id,
                file_path=arguments.file,
                filename=arguments.file.name,
            )

        elif arguments.command == "search-manual":
            result = search_manual(
                equipment_id=arguments.equipment_id,
                query=arguments.query,
            )

        elif arguments.command == "list-manuals":
            result = {
                "documents": list_manual_documents(
                    arguments.equipment_id
                )
            }

        else:
            raise ValueError(
                f"Неизвестная команда: {arguments.command}"
            )

        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            )
        )

    except (ValueError, ManualKnowledgeUnavailable) as error:
        print(
            json.dumps(
                {"error": str(error)},
                ensure_ascii=False,
            )
        )
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
