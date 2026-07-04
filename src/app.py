import streamlit as st
from streamlit_mic_recorder import mic_recorder
from services.audio_service import transcribir_audio_a_texto, sintetizar_texto_a_audio

st.title("🧪 Test del Módulo de Audio (STT + TTS)")

audio_grabado = mic_recorder(
    start_prompt="🎤 Grabar",
    stop_prompt="🛑 Detener",
    just_once=True,
    key='grabador_mic'
)

if audio_grabado:
    audio_bytes = audio_grabado['bytes']
    st.audio(audio_bytes, format="audio/wav")
    st.write(f"Tamaño: {len(audio_bytes)} bytes")

    with st.spinner("Transcribiendo..."):
        texto = transcribir_audio_a_texto(audio_bytes)

    if texto:
        st.success(f"📝 Texto transcrito: **{texto}**")

        with st.spinner("Generando audio de respuesta..."):
            audio_respuesta = sintetizar_texto_a_audio(texto)

        st.write("🔊 Reproduciendo lo que se transcribió (eco):")
        st.audio(audio_respuesta, format="audio/mp3")
    else:
        st.error("⚠️ No se pudo transcribir el audio (revisa consola/logs)")