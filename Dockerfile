# 1. Imagen base oficial de Python ligera
FROM python:3.11-slim

# 2. Configuración para que los logs de Python se vean en tiempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Directorio de trabajo dentro del contenedor
WORKDIR /app

# 4. Instalamos herramientas básicas del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 5. Copiamos e instalamos las librerías de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 6. Copiamos el resto del código del proyecto
COPY . .

# 7. Exponemos el puerto de Streamlit
EXPOSE 8501

# 8. Comando para arrancar la interfaz web
CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]