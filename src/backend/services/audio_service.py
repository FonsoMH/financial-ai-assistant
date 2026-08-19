import speech_recognition as sr
from gtts import gTTS
from io import BytesIO
from pydub import AudioSegment

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
    """Convierte texto en bytes de audio MP3 (Text-to-Speech)."""
    try:
        tts = gTTS(text=texto, lang='es', slow=False)
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp.read()
    except Exception as e:
        print(f"❌ Error en TTS: {e}")
        return b""

        