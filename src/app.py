import os
import httpx
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from src.backend.services.audio_service import transcribir_audio_a_texto, sintetizar_texto_a_audio
from src.backend.services.llm_service import (
    procesar_mensaje,
    procesar_mensaje_streaming,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
)


app = FastAPI(title="FinancialAI - Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def warmup_ollama():
    try:
        # Timeout generoso a propósito: cargar el modelo en frío desde disco
        # puede tardar más de un minuto, y si abortamos antes de que termine,
        # Ollama cancela la carga en curso — el siguiente mensaje real vuelve
        # a pagar el coste completo desde cero. Mejor esperar de verdad aquí,
        # una vez, que dejar que le toque al primer usuario.
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": "hola", "stream": False},
                timeout=180.0,
            )
        print(f"✅ Ollama precalentado con el modelo {OLLAMA_MODEL}")
    except Exception as e:
        print(f"⚠️ No se pudo precalentar Ollama: {e!r}")


@app.get("/")
def read_root():
    """Ruta de prueba para verificar que la API funciona"""
    return {"status": "ok", "message": "Backend de Financial AI funcionando perfectamente"}


class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat")
async def procesar_chat(payload: ChatRequest):
    """Contraparte en texto de /api/voice: mismo motor de razonamiento
    (procesar_mensaje), mismo hilo de conversación compartido con la voz,
    sin pasar por STT/TTS. Si el cliente cancela la petición (AbortController
    en el frontend), FastAPI cancela esta corrutina sola — no hace falta
    manejarlo a mano aquí.
    """
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="Mensaje vacío")

    respuesta = await procesar_mensaje(payload.message)
    return {"response": respuesta}


@app.post("/api/voice")
async def procesar_voz(file: UploadFile = File(...)):
    try:
        audio_bytes = await file.read()

        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Audio vacío")

        texto_usuario, error_stt = transcribir_audio_a_texto(audio_bytes)

        if error_stt:
            print(f"⚠️ STT: {error_stt}")
            respuesta_texto = texto_usuario
        else:
            print(f"🎙️ STT: El usuario dijo -> '{texto_usuario}'")

            respuesta_texto = await procesar_mensaje(texto_usuario)
            print(f"🤖 LLM: {respuesta_texto}")

        audio_respuesta_bytes = sintetizar_texto_a_audio(respuesta_texto)

        if not audio_respuesta_bytes:
            raise HTTPException(status_code=500, detail="Error en el TTS")

        return Response(
            content=audio_respuesta_bytes,
            media_type="audio/mp3"
        )

    except HTTPException:
        raise

    except Exception as e:
        print(f"❌ Error en /api/voice: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """Versión en streaming de /api/voice: recibe el audio completo del
    usuario, pero devuelve la respuesta en varios trozos (uno por frase),
    cada uno como su propio audio, en cuanto están listos.

    Protocolo por cada frase:
      1. Un frame de texto (JSON): {"type": "chunk", "text": "..."}
      2. Un frame binario inmediatamente después: los bytes del MP3 de esa frase
    Al terminar toda la respuesta: {"type": "end"}
    Si algo falla: {"type": "error", "detail": "..."}
    """
    await websocket.accept()
    try:
        while True:
            audio_bytes = await websocket.receive_bytes()

            texto_usuario, error_stt = transcribir_audio_a_texto(audio_bytes)
            if error_stt:
                print(f"⚠️ STT: {error_stt}")
                await websocket.send_json({"type": "error", "detail": error_stt})
                continue

            print(f"🎙️ STT: El usuario dijo -> '{texto_usuario}'")

            async for frase in procesar_mensaje_streaming(texto_usuario):
                print(f"🤖 LLM dice: {frase!r}")
                audio_chunk = sintetizar_texto_a_audio(frase)
                if not audio_chunk:
                    print(f"⚠️ TTS vacío para la frase: {frase!r}")
                    continue
                await websocket.send_json({"type": "chunk", "text": frase})
                await websocket.send_bytes(audio_chunk)

            await websocket.send_json({"type": "end"})

    except WebSocketDisconnect:
        print("🔌 Cliente WebSocket desconectado")
    except Exception as e:
        print(f"❌ Error en /ws/voice: {e}")
        try:
            await websocket.send_json({"type": "error", "detail": str(e)})
        except Exception:
            pass