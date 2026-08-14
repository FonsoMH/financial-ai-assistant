FROM python:3.10-slim

# Instalamos solo ffmpeg (obligatorio para pydub) y limpiamos caché de apt
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos todo el proyecto
COPY . .

# Exponemos solo el puerto de la API de Python
EXPOSE 8000

# Arrancamos el backend
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]