FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends cron rclone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x docker-entrypoint-cron.sh sync_garmin_data.sh \
    && crontab crontab

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
