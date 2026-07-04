import speech_recognition as sr
from gtts import gTTS
from io import BytesIO
from pydub import AudioSegment

def transcribir_audio_a_texto(audio_bytes: bytes) -> str:
    """Convierte bytes de audio en texto (Speech-to-Text)."""
    r = sr.Recognizer()
    try:
        # Normalizamos el audio a un WAV válido (mono, 16kHz) usando pydub/ffmpeg
        audio_segment = AudioSegment.from_file(BytesIO(audio_bytes))
        audio_segment = audio_segment.set_channels(1).set_frame_rate(16000)

        wav_io = BytesIO()
        audio_segment.export(wav_io, format="wav")
        wav_io.seek(0)

        with sr.AudioFile(wav_io) as source:
            audio_data = r.record(source)

        return r.recognize_google(audio_data, language="es-ES")
    except sr.UnknownValueError:
        print("❌ STT: No se pudo entender el audio (silencio o ruido)")
        return ""
    except sr.RequestError as e:
        print(f"❌ STT: Error de conexión con Google: {e}")
        return ""
    except Exception as e:
        print(f"❌ STT: Error inesperado: {e}")
        return ""


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