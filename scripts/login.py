"""
Вход в аккаунт Telegram и сохранение сессии.

Вход в два шага, потому что Telegram присылает код уже после запроса:

    python scripts/login.py listener запрос          # Telegram шлёт код
    python scripts/login.py listener код 12345       # подтверждаем
    python scripts/login.py listener пароль СЕКРЕТ   # если включена 2FA

Проверить готовый аккаунт:

    python scripts/login.py listener проверка

После успешного входа появляется data/<имя>.session — дальше программа
входит по нему, код больше не нужен.
"""

import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import (
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)

load_dotenv()

АККАУНТЫ = {
    "listener": ("СЛУШАТЕЛЬ", "LISTENER"),
    "assistant": ("АССИСТЕНТ", "ASSISTANT"),
    "inbox": ("ПОЧТОВЫЙ ЯЩИК", "INBOX"),
}

ПАПКА = "data"


def доступы(префикс: str) -> tuple[int, str, str]:
    api_id = os.getenv(f"{префикс}_API_ID", "").strip()
    api_hash = os.getenv(f"{префикс}_API_HASH", "").strip()
    телефон = os.getenv(f"{префикс}_PHONE", "").strip()

    нет = [
        имя
        for имя, знач in (
            (f"{префикс}_API_ID", api_id),
            (f"{префикс}_API_HASH", api_hash),
            (f"{префикс}_PHONE", телефон),
        )
        if not знач
    ]
    if нет:
        print("ОШИБКА: в .env не заполнено: " + ", ".join(нет))
        sys.exit(1)
    if not api_id.isdigit():
        print(f"ОШИБКА: {префикс}_API_ID должен быть числом, а там {api_id!r}")
        sys.exit(1)

    return int(api_id), api_hash, телефон


def путь_сессии(ключ: str) -> str:
    os.makedirs(ПАПКА, exist_ok=True)
    return os.path.join(ПАПКА, ключ)


def путь_ожидания(ключ: str) -> str:
    return os.path.join(ПАПКА, f"{ключ}.ожидание.json")


async def показать_кто(client: TelegramClient, ключ: str) -> None:
    я = await client.get_me()
    имя = " ".join(filter(None, [я.first_name, я.last_name])) or "(без имени)"
    ник = f"@{я.username}" if я.username else "(без username)"
    print(f"ИМЯ:      {имя}")
    print(f"USERNAME: {ник}")
    print(f"ID:       {я.id}")
    print(f"СЕССИЯ:   {путь_сессии(ключ)}.session")

    print("ЧАТЫ:")
    сколько = 0
    async for д in client.iter_dialogs(limit=8):
        тип = "группа" if д.is_group else "канал" if д.is_channel else "личка"
        print(f"   [{тип}] {д.name}")
        сколько += 1
    if сколько == 0:
        print("   (пусто — нормально для нового аккаунта)")


async def шаг_запрос(ключ: str) -> None:
    api_id, api_hash, телефон = доступы(АККАУНТЫ[ключ][1])
    client = TelegramClient(путь_сессии(ключ), api_id, api_hash)
    await client.connect()

    if await client.is_user_authorized():
        print("УЖЕ_ВОШЁЛ")
        await показать_кто(client, ключ)
        await client.disconnect()
        return

    результат = await client.send_code_request(телефон)
    with open(путь_ожидания(ключ), "w", encoding="utf-8") as f:
        json.dump({"phone_code_hash": результат.phone_code_hash}, f)

    print("КОД_ОТПРАВЛЕН")
    print(f"Telegram отправил код на {телефон}.")
    await client.disconnect()


async def шаг_код(ключ: str, код: str) -> None:
    api_id, api_hash, телефон = доступы(АККАУНТЫ[ключ][1])

    try:
        with open(путь_ожидания(ключ), encoding="utf-8") as f:
            phone_code_hash = json.load(f)["phone_code_hash"]
    except FileNotFoundError:
        print("ОШИБКА: сначала запроси код (шаг 'запрос')")
        sys.exit(1)

    client = TelegramClient(путь_сессии(ключ), api_id, api_hash)
    await client.connect()

    try:
        await client.sign_in(phone=телефон, code=код, phone_code_hash=phone_code_hash)
    except PhoneCodeInvalidError:
        print("НЕВЕРНЫЙ_КОД — проверь цифры и попробуй ещё раз")
        await client.disconnect()
        sys.exit(1)
    except PhoneCodeExpiredError:
        print("КОД_ПРОСРОЧЕН — запроси новый (шаг 'запрос')")
        os.remove(путь_ожидания(ключ))
        await client.disconnect()
        sys.exit(1)
    except SessionPasswordNeededError:
        print("НУЖЕН_ПАРОЛЬ — на аккаунте включена двухэтапная проверка")
        print("Следующий шаг: login.py <аккаунт> пароль <твой_пароль>")
        await client.disconnect()
        sys.exit(2)

    print("ВХОД_ВЫПОЛНЕН")
    await показать_кто(client, ключ)
    await client.disconnect()
    os.remove(путь_ожидания(ключ))


async def шаг_пароль(ключ: str, пароль: str) -> None:
    api_id, api_hash, _ = доступы(АККАУНТЫ[ключ][1])
    client = TelegramClient(путь_сессии(ключ), api_id, api_hash)
    await client.connect()
    await client.sign_in(password=пароль)

    print("ВХОД_ВЫПОЛНЕН")
    await показать_кто(client, ключ)
    await client.disconnect()

    if os.path.exists(путь_ожидания(ключ)):
        os.remove(путь_ожидания(ключ))


async def шаг_проверка(ключ: str) -> None:
    api_id, api_hash, _ = доступы(АККАУНТЫ[ключ][1])
    client = TelegramClient(путь_сессии(ключ), api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        print("НЕ_ВОШЁЛ")
        await client.disconnect()
        sys.exit(1)

    print("ВСЁ_В_ПОРЯДКЕ")
    await показать_кто(client, ключ)
    await client.disconnect()


def подсказка() -> None:
    print("Как пользоваться:")
    print("   login.py <аккаунт> запрос            — запросить код")
    print("   login.py <аккаунт> код 12345         — подтвердить код")
    print("   login.py <аккаунт> пароль СЕКРЕТ     — если включена 2FA")
    print("   login.py <аккаунт> проверка          — проверить готовый вход")
    print(f"Аккаунты: {', '.join(АККАУНТЫ)}")


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[1] not in АККАУНТЫ:
        подсказка()
        sys.exit(1)

    ключ, действие = sys.argv[1], sys.argv[2]

    if действие == "запрос":
        asyncio.run(шаг_запрос(ключ))
    elif действие == "проверка":
        asyncio.run(шаг_проверка(ключ))
    elif действие in ("код", "пароль"):
        if len(sys.argv) < 4:
            print(f"ОШИБКА: не хватает значения после '{действие}'")
            sys.exit(1)
        значение = sys.argv[3]
        asyncio.run(
            шаг_код(ключ, значение) if действие == "код" else шаг_пароль(ключ, значение)
        )
    else:
        подсказка()
        sys.exit(1)


if __name__ == "__main__":
    main()
