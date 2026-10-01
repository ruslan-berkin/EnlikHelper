import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
model = os.getenv("OPENAI_MODEL", "gpt-6-luna")

if not api_key:
    raise RuntimeError("OPENAI_API_KEY отсутствует в файле .env")

client = OpenAI(api_key=api_key)

response = client.responses.create(
    model=model,
    input=(
        "Ответь одним коротким предложением на русском: "
        "какова роль вибрации при мониторинге двигателя?"
    ),
    store=False,
)

print(f"Модель: {model}")
print(response.output_text)
