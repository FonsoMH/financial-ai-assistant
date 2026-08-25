import { WS_VOICE_ENDPOINT } from "../config/api";
import { File, Paths } from "expo-file-system";

/**
 * Envía el audio grabado por WebSocket y va invocando `onChunk` con cada
 * frase de la respuesta en cuanto llega su audio — no espera a que la
 * respuesta completa esté lista.
 *
 * @param {string} uri - URI local del archivo de audio grabado
 * @param {Object} callbacks
 * @param {(audioUri: string, text: string) => void} callbacks.onChunk - se llama por cada frase con audio listo
 * @param {() => void} callbacks.onEnd - se llama cuando la respuesta ha terminado del todo
 * @param {(detail: string) => void} callbacks.onError
 */
export function sendVoiceRecordingStreaming(uri, { onChunk, onEnd, onError }) {
  const ws = new WebSocket(WS_VOICE_ENDPOINT);
  ws.binaryType = "arraybuffer";

  let pendingText = null; // guarda el texto del frame JSON hasta que llega el binario que lo acompaña
  let chunkIndex = 0;

  ws.onopen = async () => {
    try {
      const file = new File(uri);
      const bytes = await file.bytes(); // Uint8Array con el contenido del audio grabado
      ws.send(bytes);

      // Solo borramos una vez que ya tenemos los bytes en memoria y enviados —
      // borrar antes (como hacíamos desde fuera) es una carrera de condiciones:
      // el archivo podía desaparecer antes de que diera tiempo a leerlo.
      try {
        if (file.exists) file.delete();
      } catch (cleanupErr) {
        console.log("No se pudo borrar el archivo temporal:", cleanupErr);
      }
    } catch (err) {
      console.error("Error leyendo el archivo de audio para enviarlo por WS:", err);
      onError?.("No se pudo leer el audio grabado");
      ws.close();
    }
  };

  ws.onmessage = async (event) => {
    // Frame de texto (JSON): control (chunk anunciado, fin, o error)
    if (typeof event.data === "string") {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return;
      }

      if (msg.type === "chunk") {
        pendingText = msg.text;
      } else if (msg.type === "end") {
        onEnd?.();
        ws.close();
      } else if (msg.type === "error") {
        onError?.(msg.detail || "Error del servidor");
        ws.close();
      }
      return;
    }

    // Frame binario: el MP3 de la frase que se anunció justo antes
    try {
      const audioUri = await arrayBufferToTempFile(event.data, chunkIndex);
      chunkIndex += 1;
      onChunk?.(audioUri, pendingText);
      pendingText = null;
    } catch (err) {
      console.error("Error guardando el chunk de audio recibido:", err);
      onError?.("No se pudo procesar un fragmento de audio");
    }
  };

  ws.onerror = (event) => {
    console.error("Error de WebSocket:", event.message || event);
    onError?.("Error de conexión con el backend");
  };

  // Permite cancelar desde fuera (por ejemplo, si el usuario interrumpe la reproducción)
  return () => {
    try {
      ws.close();
    } catch {
      // ya estaba cerrado, no pasa nada
    }
  };
}

// NOTA: `file.bytes()` / escribir un Uint8Array a un archivo nuevo con
// `File` son parte de la API más reciente de expo-file-system. Si tu
// versión instalada no expone estos métodos exactamente así, es la
// primera parte a revisar — dímelo con el error concreto y lo ajustamos.
async function arrayBufferToTempFile(arrayBuffer, index) {
  const bytes = new Uint8Array(arrayBuffer);
  const file = new File(Paths.cache, `voice-chunk-${Date.now()}-${index}.mp3`);
  await file.write(bytes);
  return file.uri;
}