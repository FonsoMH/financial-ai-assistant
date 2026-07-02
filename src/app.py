import streamlit as st
from streamlit_mic_recorder import mic_recorder
from gtts import gTTS
import os

st.title("🗣️ Prueba de Entrada y Salida de Voz")

st.subheader("1. Prueba el Micrófono (Entrada)")
st.write("Haz clic en 'Start recording', habla un momento y dale a 'Stop':")

# Inicializamos el componente del micrófono
audio_grabado = mic_recorder(
    start_prompt="🎤 Grabar entrada de voz",
    stop_prompt="🛑 Detener grabación",
    just_once=True,
    key='grabador_mic'
)

# Si el usuario ha grabado algo, el componente nos devuelve un diccionario con los datos
if audio_grabado:
    st.success("¡Audio capturado con éxito!")
    
    # Extraemos los bytes del audio grabado
    audio_bytes = audio_grabado['bytes']
    
    # Mostramos un reproductor para escuchar lo que hemos grabado nosotros mismos
    st.audio(audio_bytes, format="audio/wav")
    st.write(f"Tamaño del archivo de audio: {len(audio_bytes)} bytes")

st.divider()

st.subheader("2. Prueba el Altavoz (Salida)")
texto_prueba = st.text_input("Escribe algo para que el asistente lo lea:", "Sistema de audio listo para el reto.")

if st.button("Generar Voz de la IA"):
    with st.spinner("Generando audio..."):
        try:
            tts = gTTS(text=texto_prueba, lang='es', slow=False)
            archivo_audio = "test_audio.mp3"
            tts.save(archivo_audio)
            st.audio(archivo_audio, format="audio/mp3")
            os.remove(archivo_audio)
        except Exception as e:
            st.error(f"Error en salida de voz: {e}")