"""
Слушатель — читает чаты и находит людей, которые ищут юриста.

Работает в два сита:
  1. Ключевые слова — бесплатно и мгновенно, отсекает почти весь поток.
  2. Модель — разбирает только то, что просочилось.

Никому ничего не пишет. Его работа заканчивается записью в картотеку.
"""

import asyncio
import re
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient, events
from telethon.tl.types import User

from . import мозг, настройки
from .картотека import Картотека


def загрузить_слова() -> list[str]:
    """Читает ключевые слова, игнорируя комментарии и пустые строки."""
    слова = []
    for строка in настройки.ФАЙЛ_СЛОВ.read_text(encoding="utf-8").splitlines():
        строка = строка.strip()
        if строка and not строка.startswith("#"):
            слова.append(строка.lower())
    return слова


class ФильтрСлов:
    """
    Ищет ключевые слова в тексте.

    Короткие слова (до 5 букв) ищутся ТОЛЬКО целиком — иначе «утс» ловится
    внутри «отсутствие» и «начнутся», а «дги» внутри чего попало.
    Длинные ищутся по части слова, чтобы «юрист» ловил «юриста» и «юристом».
    """

    ПОРОГ_ЦЕЛИКОМ = 5

    def __init__(self, слова: list[str]):
        self.слова = слова
        self._целиком = {}
        self._часть = []
        for с in слова:
            норма = с.replace("ё", "е")
            if len(норма) < self.ПОРОГ_ЦЕЛИКОМ and " " not in норма:
                self._целиком[с] = re.compile(rf"(?<!\w){re.escape(норма)}(?!\w)")
            else:
                self._часть.append((с, норма))

    def совпадения(self, текст: str) -> list[str]:
        н = текст.lower().replace("ё", "е")
        итог = [с for с, норма in self._часть if норма in н]
        итог += [с for с, шаблон in self._целиком.items() if шаблон.search(н)]
        return итог

    def подходит(self, текст: str) -> bool:
        return bool(self.совпадения(текст))


def описание_чата(чат) -> str:
    for поле in ("title", "username", "first_name"):
        значение = getattr(чат, поле, None)
        if значение:
            return str(значение)
    return f"id{getattr(чат, 'id', '?')}"


class Слушатель:
    def __init__(self, картотека: Картотека, тихо: bool = False):
        self.картотека = картотека
        self.фильтр = ФильтрСлов(загрузить_слова())
        self.тихо = тихо  # не печатать пропущенные
        акк = настройки.СЛУШАТЕЛЬ
        self.client = TelegramClient(акк.сессия, акк.api_id, акк.api_hash)
        self.статистика = {"просмотрено": 0, "по_словам": 0, "лидов": 0, "дублей": 0}

    # --- разбор одного сообщения ----------------------------------------

    async def разобрать(self, сообщение, чат, *, живьём: bool) -> dict | None:
        """
        Проверяет одно сообщение. Возвращает словарь лида, если нашли,
        иначе None.
        """
        # белый список чатов — самая первая проверка
        if not настройки.чат_разрешён(описание_чата(чат)):
            return None

        self.статистика["просмотрено"] += 1

        текст = (сообщение.message or "").strip()
        if not текст or len(текст) < 12:
            return None

        автор = await сообщение.get_sender()
        if not isinstance(автор, User) or автор.bot or автор.is_self:
            return None

        # свежесть
        возраст = datetime.now(timezone.utc) - сообщение.date
        if возраст > timedelta(hours=настройки.СВЕЖЕСТЬ_ЧАСОВ):
            return None

        # сито 1 — слова
        попало = self.фильтр.совпадения(текст)
        if not попало:
            return None
        self.статистика["по_словам"] += 1

        # уже знаем этого человека?
        if self.картотека.есть(автор.id):
            self.статистика["дублей"] += 1
            if not self.тихо:
                print(f"   (уже в картотеке) {описание_чата(автор)}")
            return None

        # сито 2 — модель
        try:
            вывод = await asyncio.to_thread(
                мозг.классифицировать, текст, описание_чата(чат)
            )
        except мозг.ОшибкаМозга as e:
            print(f"   ! триаж не сработал: {e}")
            return None

        if вывод.get("_доллары"):
            self.картотека.записать_расход(
                настройки.МОДЕЛЬ_ТРИАЖА,
                вывод.get("_входных", 0),
                вывод.get("_выходных", 0),
                вывод["_доллары"],
            )

        if not вывод.get("это_запрос"):
            if not self.тихо:
                print(f"   (модель отсеяла) {текст[:60]}… — {вывод.get('почему','')}")
            return None

        лид = {
            "telegram_id": автор.id,
            "username": автор.username,
            "имя": " ".join(filter(None, [автор.first_name, автор.last_name])) or None,
            "чат_источник": описание_чата(чат),
            "исходный_текст": текст,
            "категория": вывод.get("категория"),
            "суть": вывод.get("суть"),
            "сумма": вывод.get("сумма") or None,
            "слова": попало[:5],
        }

        добавлен = self.картотека.добавить(
            telegram_id=лид["telegram_id"],
            username=лид["username"],
            имя=лид["имя"],
            чат_источник=лид["чат_источник"],
            исходный_текст=лид["исходный_текст"],
            категория=лид["категория"],
            суть=лид["суть"],
            сумма=лид["сумма"],
        )
        if not добавлен:
            self.статистика["дублей"] += 1
            return None

        self.статистика["лидов"] += 1
        метка = "НАЙДЕН" if живьём else "найден"
        print(f"   >>> {метка}: @{лид['username'] or '—'} | {лид['категория']} | {лид['суть']}")
        return лид

    # --- режим 1: разбор истории ----------------------------------------

    async def просканировать(self, сколько_на_чат: int = 200) -> None:
        """Проходит по истории всех чатов. Полезно для настройки фильтра."""
        await self.client.start()
        print("Сканирую историю чатов…\n")

        async for диалог in self.client.iter_dialogs():
            if не_группа(диалог):
                continue
            print(f"[чат] {диалог.name}")
            async for сообщение in self.client.iter_messages(
                диалог.entity, limit=сколько_на_чат
            ):
                await self.разобрать(сообщение, диалог.entity, живьём=False)

        self.напечатать_итог()
        await self.client.disconnect()

    # --- режим 2: слушать вживую ----------------------------------------

    async def слушать(self) -> None:
        await self.client.start()
        я = await self.client.get_me()
        print(f"Слушатель @{я.username} на связи. Жду сообщений…\n")

        @self.client.on(events.NewMessage(incoming=True))
        async def _(событие):
            чат = await событие.get_chat()
            if not getattr(чат, "megagroup", False) and not getattr(чат, "broadcast", False):
                # личка — слушателю она не интересна
                if событие.is_private:
                    return
            await self.разобрать(событие.message, чат, живьём=True)

        await self.client.run_until_disconnected()

    def напечатать_итог(self) -> None:
        с = self.статистика
        print("\n--- итог ---")
        print(f"просмотрено сообщений: {с['просмотрено']}")
        print(f"прошло фильтр слов:    {с['по_словам']}")
        print(f"признано лидами:       {с['лидов']}")
        print(f"уже были в картотеке:  {с['дублей']}")
        потрачено = self.картотека.потрачено_за_сутки()
        print(f"потрачено за сутки:    ${потрачено:.4f}")


def не_группа(диалог) -> bool:
    return not (диалог.is_group or диалог.is_channel)
