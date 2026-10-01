import json
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.rails.llm.options import RailStatus
from openai import OpenAI, OpenAIError
from pydantic import BaseModel


GUARDRAILS_DIR = Path(__file__).parent / "guardrails"
guardrails_config = RailsConfig.from_path(str(GUARDRAILS_DIR))
guardrails = LLMRails(guardrails_config)


class EquipmentAssessment(BaseModel):
    equipment_id: str
    status: Literal["normal", "attention"]
    observations: list[str]
    recommended_checks: list[str]


class MaintenanceReport(BaseModel):
    summary: str
    equipment: list[EquipmentAssessment]
    limitations: list[str]


class AIReportUnavailable(RuntimeError):
    pass


def check_report_with_guardrails(report: dict) -> None:
    report_text = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
    )

    try:
        result = guardrails.check(
            messages=[
                {
                    "role": "assistant",
                    "content": report_text,
                }
            ]
        )
    except Exception as error:
        raise AIReportUnavailable(
            "Проверка безопасности AI-отчёта временно недоступна"
        ) from error

    if result.status == RailStatus.BLOCKED:
        raise AIReportUnavailable(
            "AI-отчёт заблокирован проверкой безопасности"
        )


def generate_maintenance_report(
    equipment: list[dict],
    alerts: list[dict],
) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-6-luna")

    if not api_key:
        raise AIReportUnavailable(
            "OPENAI_API_KEY отсутствует в .env"
        )

    payload = {
        "equipment": equipment,
        "alerts": alerts,
    }

    system_prompt = """
Ты — помощник специалиста по обслуживанию промышленного оборудования.

Работай только с данными, переданными пользователем.
Не придумывай измерения, пороги, причины или характеристики оборудования.
Не ставь диагноз и не утверждай, что конкретная деталь неисправна.
Отделяй наблюдаемое превышение порога от возможной причины.
Рекомендации формулируй как безопасные проверки специалистом.
Если данных недостаточно, укажи это в limitations.
Пиши по-русски, кратко и понятно.
Поле status уже рассчитано приложением.
Копируй status для каждого оборудования без изменений.
Создай ровно один элемент equipment для каждого переданного оборудования.
Статус normal означает только отсутствие превышений в переданных измерениях,
а не подтверждение исправности оборудования.
""".strip()

    try:
        client = OpenAI(api_key=api_key)

        response = client.responses.parse(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": (
                        "Подготовь отчёт по этим данным:\n"
                        + json.dumps(
                            payload,
                            ensure_ascii=False,
                        )
                    ),
                },
            ],
            text_format=MaintenanceReport,
            store=False,
        )

    except OpenAIError as error:
        raise AIReportUnavailable(
            "OpenAI API временно недоступен"
        ) from error

    if response.output_parsed is None:
        raise AIReportUnavailable(
            "Модель не вернула структурированный отчёт"
        )

    expected_statuses = {
        item["equipment_id"]: item["status"]
        for item in equipment
    }

    returned_statuses = {
        item.equipment_id: item.status
        for item in response.output_parsed.equipment
    }

    if returned_statuses != expected_statuses:
        raise AIReportUnavailable(
            "Модель изменила рассчитанные статусы оборудования"
        )

    report = response.output_parsed.model_dump()

    check_report_with_guardrails(report)

    return report
