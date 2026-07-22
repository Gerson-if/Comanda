# Imagem de produção do Cardápio SaaS ("Comanda").
#
# Build:  docker build -t comanda .
# Rodar:  docker run -p 8000:8000 --env-file .env comanda
#
# Variáveis de ambiente obrigatórias em produção: SECRET_KEY, DATABASE_URL
# (ver .env.example). Rode as migrations antes do primeiro start:
#   docker run --env-file .env comanda flask db upgrade

FROM python:3.12-slim

# psycopg2 (driver PostgreSQL) precisa dessas libs de sistema para compilar/rodar
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN mkdir -p instance app/static/uploads

EXPOSE 8000

# --preload compartilha a app já carregada entre workers (menos memória,
# start mais rápido); --timeout maior acomoda upload/processamento de imagem.
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "--timeout", "60", "--preload", "wsgi:app"]
