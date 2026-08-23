# Reto IA UGR — Habla con tu dinero

Asistente financiero conversacional con LLM local (Ollama) y backend FastAPI. Frontend en React Native (Expo).

## Requisitos previos

- **Docker**
- **Node.js** (v18+) y npm — para el frontend
- **App Expo Go** instalada en tu móvil (Android/iOS) — para probar la app sin compilar nada
- GPU NVIDIA con drivers actualizados y al menos ~6GB de VRAM libres, para el modelo de 7B (funciona en CPU, pero mucho más lento)

## Estructura del proyecto

```
.
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── data/
│  ├── finanzas.db
├── src/
   ├── app.py                          # FastAPI, punto de entrada del backend
   ├── backend/
   │   ├── database.py                 # Init + seed de la base de datos SQLite
   │   └── services/
   │       ├── audio_service.py        # STT (Google) / TTS (gTTS)
   │       ├── db_service.py           # Skills reales: saldo, Bizum, NL2SQL
   │       └── llm_service.py          # Orquestador de tool calling con Ollama
   │
   └── frontend/                           # App React Native (Expo)
    ├── components/RecordButton.jsx
    ├── hooks/useVoiceRecorder.js
    ├── screens/{TextScreen,VoiceScreen}.jsx
    ├── services/voiceApi.js
    └── config/api.js
```

## 1. Backend: levantar los contenedores

Desde la raíz del proyecto:

```bash
docker compose up -d
```

Esto levanta dos servicios:
- `backend` (FastAPI, puerto 8000)
- `ollama` (LLM local, puerto 11434)

Comprueba que ambos están corriendo:
```bash
docker ps
```

## 2. Descargar el modelo del LLM

El proyecto usa **Qwen2.5-7B-Instruct** (con tool calling nativo, necesario para las skills de saldo/Bizum/NL2SQL). La primera vez, Ollama necesita descargar el modelo (no viene preinstalado en la imagen):

```bash
docker exec -it reto_ia_ollama ollama pull qwen2.5:7b-instruct
```

Esto tarda varios minutos según tu conexión (~4.7GB). Verifica que se completó:
```bash
docker exec -it reto_ia_ollama ollama list
```
Deberías ver `qwen2.5:7b-instruct` en la lista.

> **Si el pull falla repetidamente con timeouts** (`dial tcp ... i/o timeout` contra `*.r2.cloudflarestorage.com`), tu red puede estar bloqueando el storage de Ollama. Ver la sección de Troubleshooting más abajo — ahí está el procedimiento completo para cargar el modelo manualmente sin depender de ese storage.

## 3. Verificar que Ollama responde

```bash
curl http://localhost:11434/api/tags
```

Debería devolver JSON sin error, con `qwen2.5:7b-instruct` en la lista de modelos. Si `curl` no está disponible en tu terminal, abre esa URL directamente en el navegador.

## 4. Inicializar la base de datos

La base de datos SQLite con los movimientos ficticios se genera con `database.py`. Ejecútalo dentro del contenedor del backend:

```bash
docker exec -it reto_ia_backend python -m src.backend.database
```

Esto crea las tablas y las rellena con 12 meses de movimientos realistas (nóminas, alquiler, suscripciones, Bizum, gastos por categoría). Si vuelves a ejecutarlo, no duplica datos — el script comprueba si ya hay un usuario antes de sembrar.

## 5. Frontend (React Native / Expo)

El frontend corre fuera de Docker por ahora (más simple para probar en tu móvil físico):

```bash
cd src/frontend
npm install
npx expo start --lan
```

Escanea el QR con la app **Expo Go** desde tu móvil. La app detecta automáticamente la IP de tu PC en la red local (ver `config/api.js`), así que no hace falta configurar nada manualmente si el móvil y el PC están en la misma red.

## Variables de entorno (backend)

Ya vienen configuradas en `docker-compose.yml`, no hace falta tocarlas salvo que cambies de modelo:

| Variable | Valor por defecto | Descripción |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://ollama:11434` | URL interna del servicio Ollama |
| `OLLAMA_MODEL` | `qwen2.5:7b-instruct` | Modelo usado para razonamiento y tool calling |

## Comandos útiles

```bash
# Ver logs en vivo de todos los servicios
docker compose logs -f

# Reiniciar solo el backend tras un cambio de código o de env vars
docker compose up -d backend

# Parar todo
docker compose down

# Parar todo y borrar también los volúmenes (modelo de Ollama incluido)
docker compose down -v
```

## Troubleshooting

### El pull de Ollama falla con timeouts
**Alternativa: cargar el modelo manualmente desde un `.gguf`.**

Descarga un único archivo `.gguf` en cuantización Q4_K_M. **Usa la versión de un solo archivo, no la partida en fragmentos** — el repositorio oficial de Qwen en Hugging Face divide el 7B en 2 archivos, y Ollama no siempre reconoce bien esa relación entre fragmentos (error típico: `has 1 shards, expected 2`). La alternativa fiable es la re-subida de **bartowski**, en un único archivo:

```
https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/blob/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf
```
(~4.68GB)

Cópialo al contenedor:
```bash
docker cp .\Qwen2.5-7B-Instruct-Q4_K_M.gguf reto_ia_ollama:/tmp/model.gguf
```

**Importante:** no basta con un `Modelfile` mínimo (`FROM /tmp/model.gguf`) — sin una plantilla (`TEMPLATE`) que sepa formatear las herramientas, el modelo carga y responde con normalidad a preguntas sueltas, pero **nunca hace tool calling**, aunque parezca funcionar bien a simple vista. Crea un archivo de texto llamado `Modelfile` (sin extensión) con este contenido exacto — es la plantilla oficial de Qwen2.5 tal cual la usa el registro de Ollama, con el bloque de herramientas incluido:

```
FROM /tmp/model.gguf

TEMPLATE """{{- if .Messages }}
{{- if or .System .Tools }}<|im_start|>system
{{- if .System }}
{{ .System }}
{{- end }}
{{- if .Tools }}

# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{{- range .Tools }}
{"type": "function", "function": {{ .Function }}}
{{- end }}
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{"name": <function-name>, "arguments": <args-json-object>}
</tool_call>
{{- end }}<|im_end|>
{{ end }}
{{- range $i, $_ := .Messages }}
{{- $last := eq (len (slice $.Messages $i)) 1 -}}
{{- if eq .Role "user" }}<|im_start|>user
{{ .Content }}<|im_end|>
{{ else if eq .Role "assistant" }}<|im_start|>assistant
{{ if .Content }}{{ .Content }}
{{- else if .ToolCalls }}<tool_call>
{{ range .ToolCalls }}{"name": "{{ .Function.Name }}", "arguments": {{ .Function.Arguments }}}
{{ end }}</tool_call>
{{- end }}{{ if not $last }}<|im_end|>
{{ end }}
{{- else if eq .Role "tool" }}<|im_start|>user
<tool_response>
{{ .Content }}
</tool_response><|im_end|>
{{ end }}
{{- if and (ne .Role "assistant") $last }}<|im_start|>assistant
{{ end }}
{{- end }}
{{- else }}
{{- if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ if .Prompt }}<|im_start|>user
{{ .Prompt }}<|im_end|>
{{ end }}<|im_start|>assistant
{{ end }}{{ .Response }}{{ if .Response }}<|im_end|>{{ end }}"""

PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"
```

Cópialo y crea el modelo (con el mismo nombre que usa el resto del proyecto, para no tener que tocar el compose):
```bash
docker cp .\Modelfile reto_ia_ollama:/tmp/Modelfile
docker exec -it reto_ia_ollama ollama create qwen2.5:7b-instruct -f /tmp/Modelfile
```

**Verifica siempre que la plantilla se aplicó de verdad** antes de dar el proceso por bueno — el bloque `# Tools` con `<tools>` y `<tool_call>` tiene que aparecer:
```bash
docker exec -it reto_ia_ollama ollama show qwen2.5:7b-instruct --modelfile
```
Si en vez de eso ves algo como `TEMPLATE {{ .Prompt }}` a secas, el `create` no cogió la plantilla correcta (revisa que el archivo `Modelfile` se copió bien, sin corromperse por saltos de línea de Windows) y el tool calling no va a funcionar aunque el modelo responda con normalidad a preguntas sueltas.

### `/tmp/` dentro del contenedor de Ollama se vacía solo

Los archivos que copies a `/tmp/` con `docker cp` **no son persistentes** — viven en la capa de escritura del contenedor, no en el volumen `ollama_data`. Si recreas el contenedor de `ollama` (por ejemplo con `docker compose up --build`, o si Docker Desktop lo reinicia), `/tmp/` vuelve a estar vacío, aunque el modelo ya creado siga existiendo (ese sí vive en el volumen). Si necesitas recrear el modelo más adelante, tendrás que volver a copiar el `.gguf` y el `Modelfile`.

## Créditos técnicos

- **LLM**: Qwen2.5-7B-Instruct vía Ollama (function calling nativo)
- **TTS**: gTTS (Google Text-to-Speech, cloud)
- **STT**: Google Speech Recognition (vía `SpeechRecognition`)
- **Base de datos**: SQLite, datos ficticios generados con `Faker`