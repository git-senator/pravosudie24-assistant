FROM python:3.12-slim

# Не писать .pyc, выводить логи сразу без буфера
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Зависимости ставим отдельным слоем — тогда при правке кода
# они не переустанавливаются заново
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Папка для сессий Telegram и базы. Подключается снаружи как том,
# поэтому переживает пересборку контейнера.
RUN mkdir -p /app/data

CMD ["python", "-m", "src.main"]
