"""Какие модели доступны по нашему ключу и сколько они стоят по квоте."""

import httpx

from src import настройки

ответ = httpx.get(
    "https://generativelanguage.googleapis.com/v1beta/models",
    params={"key": настройки.GEMINI_КЛЮЧ},
    timeout=60,
)
данные = ответ.json()

for м in данные.get("models", []):
    имя = м["name"].removeprefix("models/")
    методы = м.get("supportedGenerationMethods", [])
    if "generateContent" not in методы:
        continue
    print(f"{имя:38} вход до {м.get('inputTokenLimit', '?')} токенов")
