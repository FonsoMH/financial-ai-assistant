import os
import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from src.backend.services.audio_service import transcribir_audio_a_texto, sintetizar_texto_a_audio
from src.backend.services.llm_service import procesar_mensaje, OLLAMA_BASE_URL, OLLAMA_MODEL


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
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": "hola", "stream": False},
                timeout=60.0,
            )
        print(f"✅ Ollama precalentado con el modelo {OLLAMA_MODEL}")
    except Exception as e:
        print(f"⚠️ No se pudo precalentar Ollama: {e}")


@app.get("/")
def read_root():
    """Ruta de prueba para verificar que la API funciona"""
    return {"status": "ok", "message": "Backend de Financial AI funcionando perfectamente"}


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