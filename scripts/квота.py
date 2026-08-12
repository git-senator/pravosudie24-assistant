"""Разовая проверка: жив ли ключ модели и что именно отвечает сервер."""

import httpx

from src import настройки

url = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{настройки.МОДЕЛЬ}:generateContent?key={настройки.GEMINI_КЛЮЧ}"
)
ответ = httpx.post(
    url,
    json={"contents": [{"role": "user", "parts": [{"text": "скажи ок"}]}]},
    timeout=60,
)
print("код:", ответ.status_code)
print(ответ.text[:2500])
