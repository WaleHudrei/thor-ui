FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./
COPY static/ ./static/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO

EXPOSE 5000

CMD gunicorn -w 2 -k gthread --threads 4 -b 0.0.0.0:${PORT:-5000} \
    --timeout 60 --graceful-timeout 20 \
    --access-logfile - --error-logfile - \
    app:app
