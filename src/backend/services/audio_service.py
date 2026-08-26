import os
import speech_recognition as sr
from gtts import gTTS
from io import BytesIO
from pydub import AudioSegment
from pydub.effects import speedup

# Configurables por entorno
TTS_SPEED = float(os.getenv("TTS_SPEED", "1.0"))
TTS_VOLUME_DB = float(os.getenv("TTS_VOLUME_DB", "0.0"))


def transcribir_audio_a_texto(audio_bytes: bytes) -> tuple[str, str | None]:
    """Convierte bytes de audio en texto (Speech-to-Text).

    Devuelve una tupla (texto, error). Si todo va bien, error es None.
    Si algo falla, texto es "" y error contiene un mensaje descriptivo
    del problema concreto, para poder mostrarlo en la UI.
    """
    r = sr.Recognizer()

    # Paso 1: normalización del audio con pydub/ffmpeg
    try:
        audio_segment = AudioSegment.from_file(BytesIO(audio_bytes))
        audio_segment = audio_segment.set_channels(1).set_frame_rate(16000)

        wav_io = BytesIO()
        audio_segment.export(wav_io, format="wav")
        wav_io.seek(0)
    except Exception as e:
        error = f"Error al procesar/normalizar el audio (pydub/ffmpeg): {e}"
        print(f"❌ STT: {error}")
        return "", error

    # Paso 2: lectura del WAV con speech_recognition
    try:
        with sr.AudioFile(wav_io) as source:
            audio_data = r.record(source)
    except Exception as e:
        error = f"Error al leer el WAV generado (speech_recognition.AudioFile): {e}"
        print(f"❌ STT: {error}")
        return "", error

    # Paso 3: llamada a la API de reconocimiento de Google
    try:
        texto = r.recognize_google(audio_data, language="es-ES")
        return texto, None
    except sr.UnknownValueError:
        error = "No se pudo entender el audio (silencio, ruido o volumen muy bajo)."
        print(f"❌ STT: {error}")
        return "No te he entendido, repite", error
    except sr.RequestError as e:
        error = f"Error de conexión con la API de Google Speech-to-Text: {e}"
        print(f"❌ STT: {error}")
        return "", error
    except Exception as e:
        error = f"Error inesperado durante el reconocimiento: {e}"
        print(f"❌ STT: {error}")
        return "", error


def sintetizar_texto_a_audio(texto: str) -> bytes:
    """Convierte texto en bytes de audio MP3 (Text-to-Speech) con gTTS,
    aplicando velocidad/volumen configurables por post-procesado con pydub."""
    try:
        tts = gTTS(text=texto, lang='es', slow=False)
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)

        # Si no hay ajustes que aplicar, devolvemos el MP3 de gTTS tal cual
        # (nos ahorramos el coste de decodificar/recodificar por nada).
        if TTS_SPEED == 1.0 and TTS_VOLUME_DB == 0.0:
            return fp.read()

        audio = AudioSegment.from_file(fp, format="mp3")

        if TTS_VOLUME_DB != 0.0:
            audio = audio + TTS_VOLUME_DB  # ganancia en dB, admite negativos

        if TTS_SPEED > 1.0:
            audio = speedup(audio, playback_speed=TTS_SPEED)
        elif TTS_SPEED < 1.0:
            # pydub.effects.speedup no soporta bien ralentizar (<1.0) —
            # su algoritmo de recorte de fragmentos está pensado solo para
            # acelerar. Para más lento, la única vía fiable con gTTS es su
            # propio modo `slow=True` (fijo, no es un factor ajustable).
            print("⚠️ TTS_SPEED < 1.0 no está soportado con este método; se ignora.")

        out = BytesIO()
        audio.export(out, format="mp3")
        out.seek(0)
        return out.read()
    except Exception as e:
        print(f"❌ Error en TTS: {e}")
        return b""