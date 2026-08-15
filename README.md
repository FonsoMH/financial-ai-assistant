# Asistente Virtual Inteligente - IA Agéntica Financiera

Proyecto desarrollado para el desafío técnico de la **Cátedra UGR-Unicaja de IA Responsable en Finanzas**.

## Tecnologías utilizadas
* **Lenguaje:** Python 3.11
* **Ecosistema IA:** LangChain / LangGraph
* **Base de Datos:** SQLite
* **Interfaz de Usuario:** Streamlit
* **Despliegue:** Docker

## Arquitectura del Motor de Razonamiento
El sistema utiliza un enfoque agéntico basado en *Function Calling* (Llamada a herramientas) para interactuar con bases de datos relacionales (Text-to-SQL) y simular operaciones financieras vía API.

## Cómo ejecutar el proyecto

docker compose up


Si no puedes descargar el llm con ollama pull:

Descarga qwen2.5-3b-instruct-q4_k_m.gguf  desde https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF

y luego desde donde has guardado lo descargado haz:
  docker cp .\qwen2.5-3b-instruct-q4_k_m.gguf reto_ia_ollama:/tmp/model.gguf
  docker exec -it reto_ia_ollama sh -c "echo 'FROM /tmp/model.gguf' > /tmp/Modelfile"
  docker exec -it reto_ia_ollama ollama create qwen2.5:3b-instruct -f /tmp/Modelfile






(otra terminal)
cd src/frontend
npx expo start --lan

