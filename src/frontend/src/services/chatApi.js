import { CHAT_ENDPOINT } from "../config/api";

/**
 * Manda un mensaje de texto al backend y devuelve la respuesta del agente.
 * Cancelable pasando un AbortSignal (ver useChatMessages).
 */
export async function sendChatMessage(message, signal) {
  const response = await fetch(CHAT_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message }),
    signal,
  });

  if (!response.ok) {
    let detail = `Respuesta del servidor: ${response.status}`;

    try {
      const data = await response.json();
      if (data.detail) {
        detail = data.detail;
      }
    } catch {
    }

    throw new Error(detail);
  }

  return await response.json();
}