"""
Уведомитель — шлёт карточки в почтовый ящик.

Денису приходит ровно два типа сообщений: «клиент готов» и «вопрос вне
скрипта». Больше программа его не трогает.
"""

from telethon import TelegramClient

from . import настройки


def ссылка_на_чат(клиент: dict) -> str:
    if клиент.get("username"):
        return f"https://t.me/{клиент['username']}"
    return f"tg://user?id={клиент['telegram_id']}"


def строка(метка: str, значение) -> str:
    значение = (str(значение).strip() if значение else "")
    return f"{метка}: {значение}\n" if значение else ""


class Уведомитель:
    def __init__(self, client: TelegramClient):
        self.client = client

    async def _кому(self):
        if настройки.ЯЩИК_USERNAME:
            return настройки.ЯЩИК_USERNAME
        return настройки.ЯЩИК_ID

    async def _послать(self, текст: str) -> None:
        if настройки.РЕПЕТИЦИЯ:
            print("\n[репетиция] карточка НЕ отправлена:\n" + текст)
            return
        try:
            await self.client.send_message(await self._кому(), текст, link_preview=False)
            print("\n[карточка отправлена в почтовый ящик]")
        except Exception as e:
            print(f"\n! карточка не ушла: {e}\n{текст}")

    async def карточка(self, клиент: dict, данные: dict, срочно: bool = False) -> None:
        шапка = "СРОЧНО — КЛИЕНТ ГОТОВ" if срочно else "КЛИЕНТ ГОТОВ"
        имя = клиент.get("имя") or "—"
        ник = f"@{клиент['username']}" if клиент.get("username") else "(без username)"

        текст = f"{шапка}\n\n{имя}  {ник}\n\n"
        текст += строка("Категория", данные.get("category"))
        текст += строка("Суть", данные.get("summary"))
        текст += строка("Что хочет", данные.get("wants"))
        текст += строка("Цена вопроса", данные.get("amount"))
        текст += строка("Стадия", данные.get("stage"))
        текст += строка("Срок", данные.get("deadline"))
        текст += строка("Документы", данные.get("documents"))
        текст += строка("Регион", данные.get("region"))
        текст += строка("Готовность", данные.get("readiness"))
        текст += строка("Нашли в чате", клиент.get("чат_источник"))
        текст += f"\nОткрыть чат: {ссылка_на_чат(клиент)}"

        await self._послать(текст)

    async def вопрос(self, клиент: dict, вопрос: str) -> None:
        имя = клиент.get("имя") or "—"
        ник = f"@{клиент['username']}" if клиент.get("username") else "(без username)"
        текст = (
            f"ВОПРОС ВНЕ СКРИПТА\n\n{имя}  {ник}\n\n"
            f"Спрашивает: {вопрос}\n\n"
            f"Я замолчал, отвечай сам.\n\n"
            f"Открыть чат: {ссылка_на_чат(клиент)}"
        )
        await self._послать(текст)

    async def тревога(self, текст: str) -> None:
        await self._послать(f"ТРЕВОГА\n\n{текст}")
