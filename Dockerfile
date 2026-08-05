FROM python:3.11-slim
# Directorio de trabajo
WORKDIR /app
# Dependencias del sistema (gcc es necesario para algunas libs)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
# Copiar solo requirements para aprovechar caché de capas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Copiar el resto del código
COPY . .
# Exponer puerto (Fly provee la variable $PORT)
EXPOSE 8000
# Ejecutar FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "${PORT:-8000}"]
