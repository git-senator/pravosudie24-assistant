"""
Картотека — вся память программы.

Один файл SQLite. Здесь живут найденные люди, история переписки и расходы.
API не помнит прошлых разговоров: историю подаём мы, отсюда.
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from . import настройки

# Статусы клиента
НОВЫЙ = "новый"
В_ОЧЕРЕДИ = "в_очереди"
ВЕДЁТ_АССИСТЕНТ = "ведёт_ассистент"
ГОТОВ = "готов"
ОТКАЗ = "отказ"
У_ЮРИСТА = "у_юриста"
НА_ПАУЗЕ = "на_паузе"


def сейчас() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def давность(часов: float) -> str:
    """
    Метка времени «сколько-то часов назад» в том же виде, что и сейчас().

    Сравнивать со встроенным datetime('now') нельзя: там между датой и
    временем пробел, а у нас «T» и часовой пояс — строки сравниваются
    посимвольно, и запись пятичасовой давности считалась свежей.
    """
    момент = datetime.now(timezone.utc) - timedelta(hours=часов)
    return момент.isoformat(timespec="seconds")


СХЕМА = """
CREATE TABLE IF NOT EXISTS клиенты (
    telegram_id    INTEGER PRIMARY KEY,
    username       TEXT,
    имя            TEXT,
    статус         TEXT    NOT NULL DEFAULT 'новый',
    чат_источник   TEXT,
    исходный_текст TEXT,
    категория      TEXT,
    суть           TEXT,
    сумма          TEXT,
    стадия         TEXT,
    регион         TEXT,
    найден         TEXT    NOT NULL,
    последний_контакт TEXT,
    причина_закрытия  TEXT
);

CREATE TABLE IF NOT EXISTS сообщения (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    кто         TEXT    NOT NULL,          -- 'клиент' | 'ассистент' | 'юрист'
    текст       TEXT    NOT NULL,
    время       TEXT    NOT NULL,
    FOREIGN KEY (telegram_id) REFERENCES клиенты(telegram_id)
);

CREATE INDEX IF NOT EXISTS idx_сообщения_клиент ON сообщения(telegram_id, id);

CREATE TABLE IF NOT EXISTS отправки (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    время       TEXT    NOT NULL,
    первое      INTEGER NOT NULL DEFAULT 0   -- 1 если это первое сообщение человеку
);

CREATE INDEX IF NOT EXISTS idx_отправки_время ON отправки(время);

CREATE TABLE IF NOT EXISTS расходы (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    время   TEXT NOT NULL,
    модель  TEXT NOT NULL,
    входных INTEGER NOT NULL DEFAULT 0,
    выходных INTEGER NOT NULL DEFAULT 0,
    доллары REAL NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_расходы_время ON расходы(время);

-- Какая карточка про какого клиента. Нужно, чтобы юрист мог ответить
-- на карточку в почтовом ящике и тем самым забрать клиента себе.
CREATE TABLE IF NOT EXISTS карточки (
    сообщение_id INTEGER PRIMARY KEY,
    telegram_id  INTEGER NOT NULL,
    время        TEXT    NOT NULL
);
"""


class Картотека:
    def __init__(self, путь: str | None = None):
        self.путь = путь or str(настройки.БАЗА)
        self.db = sqlite3.connect(self.путь)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(СХЕМА)
        self.db.commit()

    def закрыть(self) -> None:
        self.db.close()

    # --- клиенты ---------------------------------------------------------

    def есть(self, telegram_id: int) -> bool:
        cur = self.db.execute(
            "SELECT 1 FROM клиенты WHERE telegram_id = ?", (telegram_id,)
        )
        return cur.fetchone() is not None

    def добавить(
        self,
        telegram_id: int,
        username: str | None,
        имя: str | None,
        чат_источник: str,
        исходный_текст: str,
        категория: str | None = None,
        суть: str | None = None,
        сумма: str | None = None,
    ) -> bool:
        """Добавляет нового. Возвращает False, если человек уже известен."""
        if self.есть(telegram_id):
            return False
        self.db.execute(
            """INSERT INTO клиенты
               (telegram_id, username, имя, статус, чат_источник, исходный_текст,
                категория, суть, сумма, найден)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                telegram_id, username, имя, НОВЫЙ, чат_источник, исходный_текст,
                категория, суть, сумма, сейчас(),
            ),
        )
        self.db.commit()
        return True

    def получить(self, telegram_id: int) -> dict[str, Any] | None:
        cur = self.db.execute(
            "SELECT * FROM клиенты WHERE telegram_id = ?", (telegram_id,)
        )
        строка = cur.fetchone()
        return dict(строка) if строка else None

    def обновить(self, telegram_id: int, **поля: Any) -> None:
        if not поля:
            return
        разрешено = {
            "статус", "категория", "суть", "сумма", "стадия", "регион",
            "последний_контакт", "причина_закрытия", "username", "имя",
        }
        поля = {к: з for к, з in поля.items() if к in разрешено}
        if not поля:
            return
        кусок = ", ".join(f"{к} = ?" for к in поля)
        self.db.execute(
            f"UPDATE клиенты SET {кусок} WHERE telegram_id = ?",
            (*поля.values(), telegram_id),
        )
        self.db.commit()

    def найти_по_нику(self, ник: str) -> dict[str, Any] | None:
        ник = ник.strip().lstrip("@").lower()
        cur = self.db.execute(
            "SELECT * FROM клиенты WHERE lower(username) = ?", (ник,)
        )
        строка = cur.fetchone()
        return dict(строка) if строка else None

    def забыть(self, telegram_id: int) -> bool:
        """
        Убирает человека начисто: карточку, переписку, отправки.

        Нужно, если человек просит удалить свои данные, и удобно для
        повторных тестов — иначе слушатель считает его уже известным.
        """
        if not self.есть(telegram_id):
            return False
        for таблица in ("сообщения", "отправки", "карточки", "клиенты"):
            self.db.execute(
                f"DELETE FROM {таблица} WHERE telegram_id = ?", (telegram_id,)
            )
        self.db.commit()
        return True

    def список(self, статус: str | None = None, сколько: int = 100) -> list[dict]:
        if статус:
            cur = self.db.execute(
                "SELECT * FROM клиенты WHERE статус = ? ORDER BY найден DESC LIMIT ?",
                (статус, сколько),
            )
        else:
            cur = self.db.execute(
                "SELECT * FROM клиенты ORDER BY найден DESC LIMIT ?", (сколько,)
            )
        return [dict(с) for с in cur.fetchall()]

    def сводка_по_статусам(self) -> dict[str, int]:
        cur = self.db.execute(
            "SELECT статус, COUNT(*) AS сколько FROM клиенты GROUP BY статус"
        )
        return {с["статус"]: с["сколько"] for с in cur.fetchall()}

    # --- переписка -------------------------------------------------------

    def записать_сообщение(self, telegram_id: int, кто: str, текст: str) -> None:
        self.db.execute(
            "INSERT INTO сообщения (telegram_id, кто, текст, время) VALUES (?,?,?,?)",
            (telegram_id, кто, текст, сейчас()),
        )
        self.db.execute(
            "UPDATE клиенты SET последний_контакт = ? WHERE telegram_id = ?",
            (сейчас(), telegram_id),
        )
        self.db.commit()

    def переписка(self, telegram_id: int) -> list[dict]:
        cur = self.db.execute(
            "SELECT кто, текст, время FROM сообщения WHERE telegram_id = ? ORDER BY id",
            (telegram_id,),
        )
        return [dict(с) for с in cur.fetchall()]

    def сколько_сообщений(self, telegram_id: int) -> int:
        cur = self.db.execute(
            "SELECT COUNT(*) AS с FROM сообщения WHERE telegram_id = ?", (telegram_id,)
        )
        return cur.fetchone()["с"]

    # --- отправки (для лимитов) -----------------------------------------

    def записать_отправку(self, telegram_id: int, первое: bool) -> None:
        self.db.execute(
            "INSERT INTO отправки (telegram_id, время, первое) VALUES (?,?,?)",
            (telegram_id, сейчас(), 1 if первое else 0),
        )
        self.db.commit()

    def первых_за_период(self, часов: int) -> int:
        cur = self.db.execute(
            "SELECT COUNT(*) AS с FROM отправки WHERE первое = 1 AND время >= ?",
            (давность(часов),),
        )
        return cur.fetchone()["с"]

    def когда_последняя_первая(self) -> str | None:
        cur = self.db.execute(
            "SELECT MAX(время) AS в FROM отправки WHERE первое = 1"
        )
        return cur.fetchone()["в"]

    # --- расходы ---------------------------------------------------------

    def записать_расход(
        self, модель: str, входных: int, выходных: int, доллары: float
    ) -> None:
        self.db.execute(
            """INSERT INTO расходы (время, модель, входных, выходных, доллары)
               VALUES (?,?,?,?,?)""",
            (сейчас(), модель, входных, выходных, доллары),
        )
        self.db.commit()

    def потрачено_за_сутки(self) -> float:
        cur = self.db.execute(
            "SELECT COALESCE(SUM(доллары), 0) AS с FROM расходы WHERE время >= ?",
            (давность(24),),
        )
        return float(cur.fetchone()["с"])

    # --- карточки --------------------------------------------------------

    def запомнить_карточку(self, сообщение_id: int, telegram_id: int) -> None:
        self.db.execute(
            """INSERT OR REPLACE INTO карточки (сообщение_id, telegram_id, время)
               VALUES (?,?,?)""",
            (сообщение_id, telegram_id, сейчас()),
        )
        self.db.commit()

    def чья_карточка(self, сообщение_id: int) -> int | None:
        cur = self.db.execute(
            "SELECT telegram_id FROM карточки WHERE сообщение_id = ?", (сообщение_id,)
        )
        строка = cur.fetchone()
        return строка["telegram_id"] if строка else None

    # --- отчётность ------------------------------------------------------

    def сводка_за_сутки(self) -> dict[str, Any]:
        """Цифры для ежедневного отчёта юристу."""
        порог = давность(24)

        def одно(запрос: str, *значения) -> Any:
            return self.db.execute(запрос, значения).fetchone()[0]

        return {
            "найдено": одно(
                "SELECT COUNT(*) FROM клиенты WHERE найден >= ?", порог
            ),
            "написали_первыми": self.первых_за_период(24),
            "в_разговоре": одно(
                "SELECT COUNT(DISTINCT telegram_id) FROM сообщения WHERE время >= ?",
                порог,
            ),
            "готовых": одно(
                "SELECT COUNT(*) FROM клиенты WHERE статус = ? AND последний_контакт >= ?",
                ГОТОВ, порог,
            ),
            "отказов": одно(
                "SELECT COUNT(*) FROM клиенты WHERE статус = ? AND последний_контакт >= ?",
                ОТКАЗ, порог,
            ),
            "у_юриста": одно(
                "SELECT COUNT(*) FROM клиенты WHERE статус = ? AND последний_контакт >= ?",
                У_ЮРИСТА, порог,
            ),
            "ждут_ответа": len(self.неотвеченные()),
            "потрачено": self.потрачено_за_сутки(),
            "всего_в_картотеке": одно("SELECT COUNT(*) FROM клиенты"),
        }

    # --- долги -----------------------------------------------------------

    def неотвеченные(self, не_старше_часов: int = 24) -> list[dict]:
        """
        Кому мы остались должны ответ: последнее слово в переписке — за
        клиентом. Так бывает, когда модель была занята или программу
        перезапустили посреди разговора. Без этого человек молчит вечно.
        """
        cur = self.db.execute(
            """
            SELECT к.telegram_id, п.время AS когда
            FROM клиенты к
            JOIN сообщения п ON п.id = (
                SELECT MAX(id) FROM сообщения WHERE telegram_id = к.telegram_id
            )
            WHERE к.статус IN (?, ?, ?)
              AND п.кто = 'клиент'
              AND п.время >= ?
            ORDER BY п.время
            """,
            (НОВЫЙ, В_ОЧЕРЕДИ, ВЕДЁТ_АССИСТЕНТ, давность(не_старше_часов)),
        )
        return [dict(с) for с in cur.fetchall()]
