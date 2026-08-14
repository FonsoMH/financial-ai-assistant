from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from src.backend.services.audio_service import transcribir_audio_a_texto, sintetizar_texto_a_audio

app = FastAPI(title="FinancialAI - Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    """Ruta de prueba para verificar que la API funciona"""
    return {"status": "ok", "message": "Backend de Financial AI funcionando perfectamente"}

# --- ENDPOINT PARA CONECTAR CON TU VOICEBUTTON ---
@app.post("/api/voice")
async def procesar_voz(file: UploadFile = File(...)):
    try:
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Audio vacío")

        texto_usuario, error_stt = transcribir_audio_a_texto(audio_bytes)

        if error_stt:
            return {"error": error_stt, "status": "failed_stt"}

        print(f"🎙️ STT: El usuario dijo -> '{texto_usuario}'")

        respuesta_texto = f"He recibido tu audio. Dijiste: {texto_usuario}"

        audio_respuesta_bytes = sintetizar_texto_a_audio(respuesta_texto)

        if not audio_respuesta_bytes:
            raise HTTPException(status_code=500, detail="Error en el TTS")

        return Response(content=audio_respuesta_bytes, media_type="audio/mp3")

    except Exception as e:
        print(f"❌ Error en /api/voice: {e}")
        raise HTTPException(status_code=500, detail=str(e))