FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends cron rclone zip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x docker-entrypoint-cron.sh backup_garmin.sh \
    && crontab crontab

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
