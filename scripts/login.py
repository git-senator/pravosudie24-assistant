"""
Вход в аккаунт Telegram и сохранение сессии.

Запускается один раз для каждого аккаунта. После успешного входа
создаётся файл сессии в data/<имя>.session — дальше программа входит
по нему, без кода из СМС.

Использование:
    python scripts/login.py listener
    python scripts/login.py assistant
    python scripts/login.py inbox
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

# Какие аккаунты бывают и как называются их переменные в .env
АККАУНТЫ = {
    "listener": ("СЛУШАТЕЛЬ", "LISTENER"),
    "assistant": ("АССИСТЕНТ", "ASSISTANT"),
    "inbox": ("ПОЧТОВЫЙ ЯЩИК", "INBOX"),
}

ПАПКА_ДАННЫХ = "data"


def прочитать_доступы(префикс: str) -> tuple[int, str, str]:
    """Достаёт api_id, api_hash и телефон из .env. Падает с понятной ошибкой."""
    api_id = os.getenv(f"{префикс}_API_ID", "").strip()
    api_hash = os.getenv(f"{префикс}_API_HASH", "").strip()
    телефон = os.getenv(f"{префикс}_PHONE", "").strip()

    отсутствуют = [
        имя
        for имя, значение in (
            (f"{префикс}_API_ID", api_id),
            (f"{префикс}_API_HASH", api_hash),
            (f"{префикс}_PHONE", телефон),
        )
        if not значение
    ]
    if отсутствуют:
        print("ОШИБКА: в файле .env не заполнены строки:")
        for имя in отсутствуют:
            print(f"   {имя}")
        sys.exit(1)

    if not api_id.isdigit():
        print(f"ОШИБКА: {префикс}_API_ID должен быть числом, а там: {api_id!r}")
        sys.exit(1)

    return int(api_id), api_hash, телефон


async def войти(ключ: str) -> None:
    название, префикс = АККАУНТЫ[ключ]
    api_id, api_hash, телефон = прочитать_доступы(префикс)

    os.makedirs(ПАПКА_ДАННЫХ, exist_ok=True)
    путь_сессии = os.path.join(ПАПКА_ДАННЫХ, ключ)

    print(f"\n=== Вход в аккаунт: {название} ===")
    print(f"Телефон: {телефон}")
    print("Сейчас Telegram пришлёт код. Введи его ниже.\n")

    client = TelegramClient(путь_сессии, api_id, api_hash)
    await client.start(phone=телефон)

    я = await client.get_me()
    имя = " ".join(filter(None, [я.first_name, я.last_name])) or "(без имени)"
    ник = f"@{я.username}" if я.username else "(без имени пользователя)"

    print("\n--- Вход выполнен ---")
    print(f"Имя:       {имя}")
    print(f"Username:  {ник}")
    print(f"ID:        {я.id}")
    print(f"Сессия:    {путь_сессии}.session")

    # Проверка, что аккаунт реально видит свои чаты
    print("\nПоследние чаты (проверка связи):")
    сколько = 0
    async for диалог in client.iter_dialogs(limit=5):
        тип = "группа" if диалог.is_group else "канал" if диалог.is_channel else "личка"
        print(f"   [{тип}] {диалог.name}")
        сколько += 1
    if сколько == 0:
        print("   (чатов пока нет — это нормально для нового аккаунта)")

    await client.disconnect()
    print("\nГотово. Этот шаг для этого аккаунта больше повторять не нужно.\n")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in АККАУНТЫ:
        print("Укажи, в какой аккаунт входим:")
        for ключ, (название, _) in АККАУНТЫ.items():
            print(f"   python scripts/login.py {ключ:10s}  — {название}")
        sys.exit(1)

    asyncio.run(войти(sys.argv[1]))


if __name__ == "__main__":
    main()
