# ИИ-ассистент для Telegram

Ведёт клиентов в Telegram, пока владелец занят другим разговором: находит людей,
публично попросивших услугу, пишет им, выясняет задачу и бюджет, отсеивает
неподходящих и передаёт владельцу только готовых.

Дизайн: [`docs/superpowers/specs/2026-08-11-telegram-ai-assistant-design.md`](docs/superpowers/specs/2026-08-11-telegram-ai-assistant-design.md)

---

## Что нужно на сервере

Ubuntu 22.04+ и Docker. Больше ничего ставить не надо — Python и все библиотеки
живут внутри контейнера и системы не касаются.

## Установка

```bash
git clone <адрес репозитория>
cd <папка проекта>
cp .env.example .env
nano .env          # заполнить доступы, сохранить: Ctrl+O, Enter, Ctrl+X
docker compose build
```

## Вход в аккаунты Telegram

Делается **один раз для каждого аккаунта**. Telegram пришлёт код — ввести его в
терминале. После этого создастся файл сессии, и код больше не понадобится.

```bash
docker compose run --rm assistant python scripts/login.py listener
docker compose run --rm assistant python scripts/login.py assistant
docker compose run --rm assistant python scripts/login.py inbox
```

После успешного входа скрипт покажет имя аккаунта и список его последних чатов —
это подтверждает, что связь работает.

## Запуск

```bash
docker compose up -d          # запустить в фоне
docker compose logs -f        # смотреть, что происходит
docker compose down           # остановить
```

## Обновление

```bash
git pull && docker compose build && docker compose up -d
```

## Полное удаление с сервера

```bash
docker compose down --rmi all --volumes
cd .. && rm -rf <папка проекта>
```

От проекта не остаётся ничего — системные пакеты он не трогает.

---

## Безопасность

Эти файлы **никогда** не попадают в репозиторий (прописано в `.gitignore`):

| Файл | Почему |
|---|---|
| `.env` | ключи Claude API и доступы Telegram |
| `data/*.session` | полный вход в аккаунт **без пароля и кода из СМС** |
| `data/*.db` | переписки с клиентами |

Файл сессии равнозначен угнанному аккаунту. Не пересылать никому и никуда —
ни в чат, ни на почту, ни в облако.

## Ресурсы

Контейнер жёстко ограничен: 512 МБ памяти и половина ядра. Больше он не возьмёт
при любой поломке, поэтому соседним процессам на сервере помешать не может.
