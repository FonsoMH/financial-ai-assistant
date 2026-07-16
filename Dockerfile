FROM python:3.10-slim

# Instalar Node.js, npm y herramientas del sistema necesarias para audio
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Instalar la herramienta global de Expo (EAS CLI)
RUN npm install -g eas-cli

WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos todo el proyecto
COPY . .

# Exponemos el puerto 8000 (para la API de Python) 
# y los puertos 8081 y 19000 (para el servidor de desarrollo de Expo)
EXPOSE 8000 8081 19000

# Por defecto, arrancamos el backend en el puerto 8000
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]