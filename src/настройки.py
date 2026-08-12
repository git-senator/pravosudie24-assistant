"""
Настройки программы: читаются из .env и файлов в папке конфиг/.

Всё, что можно поменять без правки кода, собрано здесь.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

КОРЕНЬ = Path(__file__).resolve().parent.parent
ПАПКА_ДАННЫХ = КОРЕНЬ / "data"
ПАПКА_КОНФИГ = КОРЕНЬ / "конфиг"

ПАПКА_ДАННЫХ.mkdir(exist_ok=True)

БАЗА = ПАПКА_ДАННЫХ / "картотека.db"
ФАЙЛ_СКРИПТА = ПАПКА_КОНФИГ / "скрипт.md"
ФАЙЛ_СЛОВ = ПАПКА_КОНФИГ / "ключевые_слова.txt"


def _число(имя: str, по_умолчанию: int) -> int:
    try:
        return int(os.getenv(имя, "").strip() or по_умолчанию)
    except ValueError:
        return по_умолчанию


# --- Аккаунты Telegram ---------------------------------------------------

class Аккаунт:
    def __init__(self, ключ: str, префикс: str):
        self.ключ = ключ
        self.api_id = _число(f"{префикс}_API_ID", 0)
        self.api_hash = os.getenv(f"{префикс}_API_HASH", "").strip()
        self.телефон = os.getenv(f"{префикс}_PHONE", "").strip()
        self.сессия = str(ПАПКА_ДАННЫХ / ключ)

    @property
    def заполнен(self) -> bool:
        return bool(self.api_id and self.api_hash)


СЛУШАТЕЛЬ = Аккаунт("listener", "LISTENER")
АССИСТЕНТ = Аккаунт("assistant", "ASSISTANT")

# Почтовый ящик: только адрес, ключи не нужны — пишет ему Ассистент
ЯЩИК_USERNAME = os.getenv("INBOX_USERNAME", "").strip().lstrip("@")
ЯЩИК_ID = _число("INBOX_ID", 0)


# --- Мозг ----------------------------------------------------------------

МОДЕЛЬ = os.getenv("MODEL", "gemini-3.6-flash").strip()
GEMINI_КЛЮЧ = os.getenv("GEMINI_API_KEY", "").strip()
ANTHROPIC_КЛЮЧ = os.getenv("ANTHROPIC_API_KEY", "").strip()

# Модель для триажа лидов — задача простая, берём самую дешёвую
МОДЕЛЬ_ТРИАЖА = os.getenv("MODEL_TRIAGE", "").strip() or МОДЕЛЬ


# --- Лимиты отправки -----------------------------------------------------
# Верхние границы захардкожены: конфиг может понизить, но не поднять.
# Это защита аккаунта, а не настройка.

_ПОТОЛОК_В_ЧАС = 5
_ПОТОЛОК_В_СУТКИ = 20

ПЕРВЫХ_В_ЧАС = min(_число("FIRST_PER_HOUR", 3), _ПОТОЛОК_В_ЧАС)
ПЕРВЫХ_В_СУТКИ = min(_число("FIRST_PER_DAY", 15), _ПОТОЛОК_В_СУТКИ)

ПАУЗА_МИН_СЕК = _число("PAUSE_MIN_SEC", 8 * 60)
ПАУЗА_МАКС_СЕК = _число("PAUSE_MAX_SEC", 20 * 60)

ТИХО_С = _число("QUIET_FROM", 22)   # с какого часа не писать
ТИХО_ДО = _число("QUIET_TO", 9)     # до какого часа не писать
ЧАСОВОЙ_ПОЯС = os.getenv("TIMEZONE", "Europe/Moscow").strip()


# --- Прочие ограничители -------------------------------------------------

СООБЩЕНИЙ_НА_КЛИЕНТА = _число("MAX_MESSAGES_PER_CLIENT", 25)

# Как часто проверять, не остался ли кто-то без ответа, и через сколько
# минут молчания звать юриста на помощь
СЕКУНД_ДОГОНЯТЬ = _число("CATCHUP_SECONDS", 90)
ТРЕВОГА_ЧЕРЕЗ_МИНУТ = _число("ALERT_AFTER_MINUTES", 20)
ЛИМИТ_ТРАТ_В_СУТКИ = float(os.getenv("DAILY_SPEND_LIMIT", "5").strip() or 5)

# Сообщения старше этого возраста считаем протухшими и не берём
СВЕЖЕСТЬ_ЧАСОВ = _число("FRESHNESS_HOURS", 24)

# Режим репетиции: всё работает, но наружу ничего не уходит
РЕПЕТИЦИЯ = os.getenv("DRY_RUN", "1").strip().lower() in ("1", "true", "yes", "да")

# Белый список чатов. Если заполнен — слушаем ТОЛЬКО их, остальные не трогаем.
# Пусто = слушаем все чаты, где сидит Ридик.
# Задаётся названиями через запятую, регистр не важен.
ТОЛЬКО_ЧАТЫ = [
    ч.strip().lower()
    for ч in os.getenv("CHATS_ONLY", "").split(",")
    if ч.strip()
]


def чат_разрешён(название: str) -> bool:
    if not ТОЛЬКО_ЧАТЫ:
        return True
    н = (название or "").lower()
    return any(ч in н for ч in ТОЛЬКО_ЧАТЫ)


def проверить() -> list[str]:
    """Возвращает список проблем в настройках. Пустой список — всё хорошо."""
    беды = []
    if not СЛУШАТЕЛЬ.заполнен:
        беды.append("не заполнены LISTENER_API_ID / LISTENER_API_HASH")
    if not АССИСТЕНТ.заполнен:
        беды.append("не заполнены ASSISTANT_API_ID / ASSISTANT_API_HASH")
    if not (ЯЩИК_USERNAME or ЯЩИК_ID):
        беды.append("не указан почтовый ящик (INBOX_USERNAME или INBOX_ID)")
    if МОДЕЛЬ.startswith("gemini") and not GEMINI_КЛЮЧ:
        беды.append("выбрана модель Gemini, но GEMINI_API_KEY пуст")
    if МОДЕЛЬ.startswith("claude") and not ANTHROPIC_КЛЮЧ:
        беды.append("выбрана модель Claude, но ANTHROPIC_API_KEY пуст")
    if not ФАЙЛ_СКРИПТА.exists():
        беды.append(f"нет файла скрипта: {ФАЙЛ_СКРИПТА}")
    if not ФАЙЛ_СЛОВ.exists():
        беды.append(f"нет файла ключевых слов: {ФАЙЛ_СЛОВ}")
    return беды
