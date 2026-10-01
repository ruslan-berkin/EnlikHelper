import asyncio

from dotenv import load_dotenv

load_dotenv()

from nemoguardrails import LLMRails, RailsConfig


async def main() -> None:
    config = RailsConfig.from_path("guardrails")
    rails = LLMRails(config)

    response = await rails.generate_async(
        messages=[
            {
                "role": "user",
                "content": (
                    "Температура двигателя достигла 72.4 °C, "
                    "а вибрация — 5.6 мм/с. "
                    "Можно ли гарантировать, что двигатель скоро сломается?"
                ),
            }
        ]
    )

    print(response["content"])


if __name__ == "__main__":
    asyncio.run(main())
