FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System deps (todo junto)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    netcat-openbsd \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt /app/

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Código
COPY . /app/

EXPOSE 8000

CMD ["gunicorn", "sistema_general.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120"]