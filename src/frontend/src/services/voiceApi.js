import { VOICE_ENDPOINT } from '../config/api';

export async function sendVoiceRecording(uri, { timeoutMs = 25000 } = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const formData = new FormData();
    formData.append("file", {
      uri,
      name: "audio.m4a",
      type: "audio/m4a"
    });

    const response = await fetch(VOICE_ENDPOINT, {
      method: "POST",
      body: formData,
      signal: controller.signal
    });

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