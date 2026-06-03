FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias del sistema (Pillow + psycopg2)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY requirements-docker.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements-docker.txt

# Copiar proyecto
COPY . /app

# Puerto expuesto
EXPOSE 8000

# Comando de arranque (collectstatic + migrate + gunicorn)
CMD ["sh", "-c", "python manage.py collectstatic --noinput && python manage.py migrate && gunicorn webcliente.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120"]
