import { VOICE_ENDPOINT } from '../config/api';

export async function sendVoiceRecording(uri, { timeoutMs = 25000 } = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const t0 = Date.now();
  console.log(`📤 [${t0}] Empezando envío a ${VOICE_ENDPOINT} (uri=${uri})`);

  try {
    const formData = new FormData();
    formData.append("file", {
      uri,
      name: "audio.m4a",
      type: "audio/m4a"
    });

    let response;
    try {
      response = await fetch(VOICE_ENDPOINT, {
        method: "POST",
        body: formData,
        signal: controller.signal
      });
    } catch (fetchErr) {
      const t1 = Date.now();
      console.log(
        `❌ [${t1}] fetch() lanzó excepción tras ${t1 - t0}ms — name=${fetchErr.name} message=${fetchErr.message}`
      );
      throw fetchErr;
    }

    const t1 = Date.now();
    console.log(`✅ [${t1}] Respuesta recibida tras ${t1 - t0}ms — status=${response.status}`);

    if (!response.ok) {
      let detail = `Respuesta del servidor: ${response.status}`;

      try {
        const data = await response.json();

        if (data.detail) {
          detail = data.detail;
        }
      } catch {
        // La respuesta no es JSON, no hacemos nada y usamos el mensaje de error por defecto
      }

      throw new Error(detail);
    }

    return await response.blob();
  } finally {
    clearTimeout(timeoutId);
  }
}