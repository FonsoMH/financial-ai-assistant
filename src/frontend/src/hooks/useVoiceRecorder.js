import { useCallback, useEffect, useRef, useState } from "react";
import { Platform } from "react-native";
import {
  useAudioRecorder,
  useAudioPlayer,
  useAudioPlayerStatus,
  RecordingPresets,
  setAudioModeAsync,
  requestRecordingPermissionsAsync,
} from "expo-audio";
import { File } from "expo-file-system";
import { sendVoiceRecordingStreaming } from "../services/voiceWebSockets";

// Estados posibles: idle -> recording -> sending -> playing -> idle
// Desde "playing" se puede volver directamente a "recording" (interrupción)
export function useVoiceRecorder() {
  const [status, setStatus] = useState("idle");
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const player = useAudioPlayer(null);
  const playerStatus = useAudioPlayerStatus(player);
  const hasPermission = useRef(false);

  // Lock síncrono: evita que un segundo toque dispare una transición
  // mientras la anterior sigue en curso (React aún no ha repintado el
  // nuevo `status`, así que confiar solo en `status` deja una ventana
  // de carrera entre toques rápidos).
  const busyRef = useRef(false);

  // Cola de audios pendientes de reproducir (llegan uno a uno por WebSocket)
  // y la función para cancelar la conexión WS en curso si hace falta.
  const audioQueueRef = useRef([]);
  const isPlayingQueueRef = useRef(false);
  const cancelWsRef = useRef(null);

  useEffect(() => {
    (async () => {
      const perm = await requestRecordingPermissionsAsync();
      hasPermission.current = perm.granted;
      await setAudioModeAsync({
        allowsRecording: true,
        playsInSilentMode: true,
        shouldRouteThroughEarpiece: false, // solo tiene efecto en Android
      });
    })();
  }, []);

  // En iOS, `shouldRouteThroughEarpiece` no hace nada (limitación conocida
  // de expo-audio, issue #43086) — el enrutamiento al auricular viene de
  // la categoría "PlayAndRecord" en sí. La única forma de forzar el
  // altavoz principal es desactivar `allowsRecording` justo antes de
  // reproducir, y reactivarlo antes de grabar.
  //
  // OJO: alternar el modo de audio por turno es justo lo que evitábamos
  // (costaba varios segundos de asentamiento de la sesión). Aquí lo
  // limitamos a iOS y a una vez por turno (no por cada chunk de audio),
  // pero mide la latencia real en iOS tras aplicar esto — si reaparece
  // el retraso, es la señal de que este trade-off no compensa.
  const ensureIosPlaybackRoute = useCallback(async () => {
    if (Platform.OS !== "ios") return;
    await setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true });
  }, []);

  const ensureIosRecordingRoute = useCallback(async () => {
    if (Platform.OS !== "ios") return;
    await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
  }, []);

  // Cuando termina de sonar un trozo de la cola, encadena el siguiente.
  // Si no queda nada más y la respuesta ya ha terminado de llegar,
  // volvemos a idle (esto lo decide playNextInQueue, es el único sitio
  // que debe tocar el status al terminar de reproducir).
  useEffect(() => {
    if (playerStatus.didJustFinish) {
      playNextInQueue();
    }
  }, [playerStatus.didJustFinish]);

  function playNextInQueue() {
    const next = audioQueueRef.current.shift();
    if (next) {
      player.replace({ uri: next });
      player.play();
      isPlayingQueueRef.current = true;
    } else {
      isPlayingQueueRef.current = false;
      // Si ya no hay más y la respuesta terminó, cerramos el turno.
      // (streamEndedRef se marca en onEnd, ver stopRecordingAndSend)
      if (streamEndedRef.current) {
        setStatus("idle");
      }
    }
  }

  const streamEndedRef = useRef(false);

  const startRecording = useCallback(async () => {
    if (!hasPermission.current) {
      const perm = await requestRecordingPermissionsAsync();
      hasPermission.current = perm.granted;
      if (!perm.granted) return;
    }
    await ensureIosRecordingRoute();
    await recorder.prepareToRecordAsync();
    recorder.record();
    setStatus("recording");
  }, [recorder, ensureIosRecordingRoute]);

  function cleanupFile(uri) {
    try {
      const file = new File(uri);
      if (file.exists) {
        file.delete();
      }
    } catch (err) {
      console.log("No se pudo borrar el archivo temporal:", err);
    }
  }

  const stopRecordingAndSend = useCallback(async () => {
    setStatus("sending");

    let uri;
    try {
      await recorder.stop();
      uri = recorder.uri;
    } catch (err) {
      console.error("Error al parar la grabación:", err);
      setStatus("idle");
      return;
    }

    if (!uri) {
      setStatus("idle");
      return;
    }

    audioQueueRef.current = [];
    isPlayingQueueRef.current = false;
    streamEndedRef.current = false;

    cancelWsRef.current = sendVoiceRecordingStreaming(uri, {
      onChunk: async (audioUri) => {
        // El primer chunk que llega dispara el paso de "sending" a "playing"
        // y arranca la reproducción; los siguientes solo se encolan.
        if (!isPlayingQueueRef.current) {
          await ensureIosPlaybackRoute();
          setStatus("playing");
          audioQueueRef.current.push(audioUri);
          playNextInQueue();
        } else {
          audioQueueRef.current.push(audioUri);
        }
      },
      onEnd: () => {
        streamEndedRef.current = true;
        // Si para cuando termina de llegar texto ya no queda nada sonando
        // ni en cola, cerramos aquí; si no, playNextInQueue() lo cerrará
        // en cuanto se vacíe la cola.
        if (!isPlayingQueueRef.current && audioQueueRef.current.length === 0) {
          setStatus("idle");
        }
      },
      onError: (detail) => {
        console.error("Error enviando audio al backend:", detail);
        setStatus("idle");
      },
    });
  }, [recorder, player]);

  const interruptPlaybackAndRecord = useCallback(async () => {
    player.pause();
    cancelWsRef.current?.();
    audioQueueRef.current = [];
    isPlayingQueueRef.current = false;
    await startRecording();
  }, [player, startRecording]);

  const toggle = useCallback(async () => {
    if (busyRef.current) return; // toque ignorado: hay una transición en curso
    busyRef.current = true;
    try {
      switch (status) {
        case "idle":
          await startRecording();
          break;
        case "recording":
          await stopRecordingAndSend();
          break;
        case "playing":
          await interruptPlaybackAndRecord();
          break;
        case "sending":
          break; // no debería llegar aquí (busyRef ya lo bloquea antes), pero por claridad
      }
    } finally {
      busyRef.current = false;
    }
  }, [status, startRecording, stopRecordingAndSend, interruptPlaybackAndRecord]);

  return {
    status,
    active: status === "recording",
    isSending: status === "sending",
    isPlaying: status === "playing",
    toggle,
  };
}