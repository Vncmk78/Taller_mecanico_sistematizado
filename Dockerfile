# Contexto: raíz del repositorio. Una instancia por Gateway o microservicio.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 10001 --create-home app

# Copias explícitas: no se incluye backend/.env ni el entorno virtual.
COPY backend/gateway ./gateway
COPY backend/services ./services
COPY backend/shared ./shared
COPY backend/scripts ./scripts

USER app
EXPOSE 8000
CMD ["python", "scripts/iniciar_servicio.py"]
