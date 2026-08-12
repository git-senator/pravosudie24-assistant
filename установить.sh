#!/usr/bin/env bash
#
# Установка ассистента на чистый сервер.
# Ничего в системе не меняет: только готовит файл настроек и собирает контейнер.
#
#     bash установить.sh
#
set -euo pipefail

cd "$(dirname "$0")"

echo "=== 1. Проверяю Docker ==="
if ! command -v docker >/dev/null 2>&1; then
    echo "Docker не установлен."
    echo "Поставьте его командой:  curl -fsSL https://get.docker.com | sh"
    exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
    echo "Установлен Docker без 'compose'. Нужен Docker версии 20.10 или новее."
    exit 1
fi
echo "Docker на месте: $(docker --version)"

echo
echo "=== 2. Файл настроек ==="
if [ -f .env ]; then
    echo ".env уже есть — не трогаю."
else
    cp .env.example .env
    chmod 600 .env
    echo "Создал .env из образца. Права 600: читать может только владелец."
fi

echo
echo "=== 3. Папка для данных ==="
mkdir -p data
chmod 700 data
echo "data/ готова (сессии Telegram и база лежат здесь)."

echo
echo "=== 4. Собираю контейнер ==="
docker compose build

echo
echo "======================================================================"
echo "Готово. Дальше по порядку:"
echo
echo "  1. Заполнить доступы:"
echo "       nano .env"
echo
echo "  2. Войти в аккаунты Telegram (код придёт на телефон):"
echo "       docker compose run --rm assistant python scripts/login.py listener запрос"
echo "       docker compose run --rm assistant python scripts/login.py listener код 12345"
echo "       docker compose run --rm assistant python scripts/login.py assistant запрос"
echo "       docker compose run --rm assistant python scripts/login.py assistant код 12345"
echo
echo "  3. Проверить, что всё заполнено:"
echo "       docker compose run --rm assistant python -m src.main проверка"
echo
echo "  4. Запустить (пока в режиме репетиции, DRY_RUN=1):"
echo "       docker compose up -d && docker compose logs -f"
echo
echo "Подробности — в README.md"
echo "======================================================================"
