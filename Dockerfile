FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_MODE=google \
    PORT=8080 \
    TELEMETRY_DIR=/tmp/fridgeagent-telemetry

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home --uid 10001 appuser
COPY . .
RUN chown -R appuser:appuser /app
USER appuser

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
