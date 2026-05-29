FROM python:3.11-slim

# variables recomendadas
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Directorio de trabajo
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# copiar requirements
COPY requirements.txt .

#isntalar dependencias de python
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# copiar proyecto
COPY . /app

# Puerto (Render lo utiliza)
EXPOSE 8000

# comandos de arranque
CMD ["gunicorn", "wsgi:application", "--bind", "0.0.0.0:8000"]