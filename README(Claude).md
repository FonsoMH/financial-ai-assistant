# Reto IA UGR — Habla con tu dinero

Asistente financiero conversacional con LLM local (Ollama), TTS local (Kokoro) y backend FastAPI. Frontend en React Native (Expo).

## Requisitos previos

- **Docker Desktop** (con WSL2 en Windows) — https://www.docker.com/products/docker-desktop/
- **Node.js** (v18+) y npm — para el frontend
- **App Expo Go** instalada en tu móvil (Android/iOS) — para probar la app sin compilar nada
- Opcional: GPU NVIDIA con drivers actualizados, para acelerar Ollama y Kokoro (si no tienes, todo funciona igual en CPU, algo más lento)

## Estructura del proyecto

```
.
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── src/
│   ├── app.py                          # FastAPI, punto de entrada del backend
│   └── backend/
│       ├── database.py                 # Init + seed de la base de datos SQLite
│       └── services/
│           └── audio_service.py        # STT / TTS
└── frontend/                           # App React Native (Expo)
    ├── components/RecordButton.jsx
    ├── hooks/useVoiceRecorder.js
    ├── screens/{TextScreen,VoiceScreen}.jsx
    ├── services/voiceApi.js
    └── config/api.js
```

## 1. Backend: levantar los contenedores

Desde la raíz del proyecto:

```powershell
docker compose up -d
```

Esto levanta tres servicios:
- `backend` (FastAPI, puerto 8000)
- `ollama` (LLM local, puerto 11434)
- `kokoro` (TTS local, puerto 8880)

Comprueba que los tres están corriendo:
```powershell
docker ps
```

## 2. Descargar el modelo del LLM

La primera vez, Ollama necesita descargar el modelo (no viene preinstalado en la imagen):

```powershell
docker exec -it reto_ia_ollama ollama pull qwen2.5:3b-instruct
```

Esto tarda unos minutos según tu conexión (~2GB). Verifica que se completó:
```powershell
docker exec -it reto_ia_ollama ollama list
```
Deberías ver `qwen2.5:3b-instruct` en la lista.

> **Si el pull falla repetidamente con timeouts** (`dial tcp ... i/o timeout` contra `*.r2.cloudflarestorage.com`), tu red puede estar bloqueando el storage de Ollama. Ver la sección de Troubleshooting más abajo.

## 3. Verificar que los servicios responden

```powershell
curl http://localhost:11434/api/tags
curl http://localhost:8880/v1/audio/voices
```

Ambos deberían devolver JSON sin error. Si `curl` no está disponible en tu PowerShell, abre esas URLs directamente en el navegador.

## 4. Inicializar la base de datos

La base de datos SQLite con los movimientos ficticios se genera con `database.py`. Ejecútalo dentro del contenedor del backend:

```powershell
docker exec -it reto_ia_backend python -m src.backend.database
```

Esto crea las tablas y las rellena con 12 meses de movimientos realistas (nóminas, alquiler, suscripciones, Bizum, gastos por categoría). Si vuelves a ejecutarlo, no duplica datos — el script comprueba si ya hay un usuario antes de sembrar.

## 5. Frontend (React Native / Expo)

El frontend corre fuera de Docker por ahora (más simple para probar en tu móvil físico):

```powershell
cd frontend
npm install
npx expo start --tunnel
```

Escanea el QR con la app **Expo Go** desde tu móvil. La app detecta automáticamente la IP de tu PC en la red local (ver `config/api.js`), así que no hace falta configurar nada manualmente si el móvil y el PC están en la misma red — el flag `--tunnel` además permite probarlo aunque no estén en la misma red local.

## Variables de entorno (backend)

Ya vienen configuradas en `docker-compose.yml`, no hace falta tocarlas salvo que cambies de modelo:

| Variable | Valor por defecto | Descripción |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://ollama:11434` | URL interna del servicio Ollama |
| `KOKORO_BASE_URL` | `http://kokoro:8880` | URL interna del servicio Kokoro |
| `OLLAMA_MODEL` | `qwen2.5:3b-instruct` | Modelo usado para razonamiento y tool calling |

## Comandos útiles

```powershell
# Ver logs en vivo de todos los servicios
docker compose logs -f

# Reiniciar solo el backend tras un cambio de código o de env vars
docker compose up -d

# Parar todo
docker compose down

# Parar todo y borrar también los volúmenes (modelo de Ollama incluido)
docker compose down -v
```

## Troubleshooting

**El pull de Ollama falla con timeouts contra `r2.cloudflarestorage.com`**
Algunas redes (campus universitarios, ciertos ISPs) bloquean ese storage concreto de Cloudflare. Confírmalo probando `curl.exe -v https://dd20bb891979d25aebc8bec07b2b3bbc.r2.cloudflarestorage.com` desde tu terminal, fuera de Docker: si también falla ahí, es la red, no Docker.

Alternativa: descarga el `.gguf` del modelo manualmente desde Hugging Face (`https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF`, variante `q4_k_m`) y créalo como modelo local:
```powershell
docker cp .\qwen2.5-3b-instruct-q4_k_m.gguf reto_ia_ollama:/tmp/model.gguf
docker exec -it reto_ia_ollama sh -c "echo 'FROM /tmp/model.gguf' > /tmp/Modelfile"
docker exec -it reto_ia_ollama ollama create qwen2.5:3b-instruct -f /tmp/Modelfile
```
Usar el mismo nombre (`qwen2.5:3b-instruct`) que el tag oficial evita tener que tocar nada más en el compose.

**Docker Desktop tarda mucho en arrancar tras un `wsl --shutdown`**
Es normal que tarde algo más de lo habitual (reinicializa las distros WSL2 desde cero). Si pasan más de 5 minutos en "Starting...", cierra Docker Desktop del todo y vuelve a abrirlo.

**El móvil no conecta con el backend**
Asegúrate de que el móvil y el PC están en la misma red Wi-Fi, o usa `npx expo start --tunnel` para evitar depender de la red local.

## Créditos técnicos

- **LLM**: Qwen2.5-3B-Instruct vía Ollama (function calling nativo)
- **TTS**: Kokoro-82M vía servidor compatible con la API de OpenAI
- **STT**: Google Speech Recognition (vía `SpeechRecognition`)
- **Base de datos**: SQLite, datos ficticios generados con `Faker`