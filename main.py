import argparse
import csv
from pathlib import Path
from database import (
    count_readings,
    get_alert_readings,
    get_equipment_summaries,
    initialize_database,
    save_readings,
    set_equipment_thresholds,
)

REQUIRED_COLUMNS = {
    "timestamp",
    "equipment_id",
    "temperature_c",
    "vibration_mm_s",
    "rpm",
}

MAX_TEMPERATURE_C = 70.0
MAX_VIBRATION_MM_S = 4.5


def load_readings(file_path: Path) -> list[dict]:
    readings = []

    if not file_path.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    with file_path.open(encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)

        actual_columns = set(reader.fieldnames or [])
        missing_columns = REQUIRED_COLUMNS - actual_columns

        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"В CSV отсутствуют колонки: {missing}")

        for line_number, row in enumerate(reader, start=2):
            try:
                reading = {
                    "timestamp": row["timestamp"].strip(),
                    "equipment_id": row["equipment_id"].strip(),
                    "temperature_c": float(row["temperature_c"]),
                    "vibration_mm_s": float(row["vibration_mm_s"]),
                    "rpm": int(row["rpm"]),
                }
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"Некорректные данные в строке {line_number}"
                ) from error

            if not reading["timestamp"]:
                raise ValueError(f"Пустое время в строке {line_number}")

            if not reading["equipment_id"]:
                raise ValueError(f"Пустой equipment_id в строке {line_number}")

            if reading["rpm"] < 0:
                raise ValueError(f"RPM не может быть отрицательным: строка {line_number}")

            readings.append(reading)

    if not readings:
        raise ValueError("CSV не содержит измерений")

    return readings


def find_alerts(readings: list[dict]) -> list[dict]:
    alerts = []

    for reading in readings:
        reasons = []

        if reading["temperature_c"] >= reading["max_temperature_c"]:
            reasons.append(
                f"температура {reading['temperature_c']:.1f} °C "
                f"(порог {reading['max_temperature_c']:.1f} °C)"
            )

        if reading["vibration_mm_s"] >= reading["max_vibration_mm_s"]:
            reasons.append(
                f"вибрация {reading['vibration_mm_s']:.1f} мм/с "
                f"(порог {reading['max_vibration_mm_s']:.1f} мм/с)"
            )

        alerts.append(
            {
                "timestamp": reading["timestamp"],
                "equipment_id": reading["equipment_id"],
                "reasons": reasons,
            }
        )

    return alerts


def print_summary(summary: dict) -> None:
    print(f"Оборудование: {summary['equipment_id']}")
    print(f"Количество измерений: {summary['readings_count']}")
    print(f"Средняя температура: {summary['avg_temperature']:.1f} °C")
    print(f"Максимальная температура: {summary['max_temperature']:.1f} °C")
    print(f"Средняя вибрация: {summary['avg_vibration']:.2f} мм/с")
    print(f"Максимальная вибрация: {summary['max_vibration']:.2f} мм/с")


def print_alerts(alerts: list[dict]) -> None:
    print("\nПредупреждения:")

    if not alerts:
        print("Опасные значения не обнаружены")
        return

    for alert in alerts:
        reasons = ", ".join(alert["reasons"])
        print(
    f"- {alert['equipment_id']} — "
    f"{alert['timestamp']}: {reasons}"
)


def import_file(file_path: Path) -> None:
    readings = load_readings(file_path)
    inserted_count = save_readings(readings)

    print(f"Файл обработан: {file_path}")
    print(f"Измерений в файле: {len(readings)}")
    print(f"Добавлено новых измерений: {inserted_count}")
    print(f"Всего измерений в базе: {count_readings()}")


def show_report() -> None:
    summaries = get_equipment_summaries()

    if not summaries:
        print("В базе пока нет измерений")
        return

    for summary in summaries:
        print_summary(summary)

    alert_readings = get_alert_readings()
    alerts = find_alerts(alert_readings)
    print_alerts(alerts)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Анализ показаний промышленного оборудования"
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    import_command = commands.add_parser(
        "import",
        help="Загрузить измерения из CSV",
    )
    import_command.add_argument(
        "file",
        type=Path,
        help="Путь к CSV-файлу",
    )

    commands.add_parser(
        "report",
        help="Показать отчёт из базы данных",
    )
    thresholds_command = commands.add_parser(
        "thresholds",
        help="Изменить пороги оборудования",
    )
    thresholds_command.add_argument(
        "equipment_id",
        help="Идентификатор оборудования",
    )
    thresholds_command.add_argument(
        "--temperature",
        type=float,
        required=True,
        help="Максимальная температура",
    )
    thresholds_command.add_argument(
        "--vibration",
        type=float,
        required=True,
        help="Максимальная вибрация",
    )
    return parser

def update_thresholds(
    equipment_id: str,
    temperature: float,
    vibration: float,
) -> None:
    if temperature <= 0:
        raise ValueError("Порог температуры должен быть больше нуля")

    if vibration <= 0:
        raise ValueError("Порог вибрации должен быть больше нуля")

    updated = set_equipment_thresholds(
        equipment_id,
        temperature,
        vibration,
    )

    if not updated:
        raise ValueError(
            f"Оборудование не найдено: {equipment_id}"
        )

    print(f"Пороги обновлены для {equipment_id}")
    print(f"Температура: {temperature:.1f} °C")
    print(f"Вибрация: {vibration:.1f} мм/с")

def main() -> None:
    initialize_database()
    parser = create_parser()
    arguments = parser.parse_args()

    try:
        if arguments.command == "import":
            import_file(arguments.file)

        elif arguments.command == "report":
            show_report()
            
        elif arguments.command == "thresholds":
            update_thresholds(
                arguments.equipment_id,
                arguments.temperature,
                arguments.vibration,
            )

    except (FileNotFoundError, ValueError) as error:
        print(f"Ошибка: {error}")


if __name__ == "__main__":
    main()
