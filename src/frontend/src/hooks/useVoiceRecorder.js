import { useCallback, useEffect, useRef, useState } from "react";
import {
  useAudioRecorder,
  useAudioPlayer,
  useAudioPlayerStatus,
  RecordingPresets,
  setAudioModeAsync,
  requestRecordingPermissionsAsync,
} from "expo-audio";
import { File } from "expo-file-system";
import { sendVoiceRecording } from "../services/voiceApi";

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

  useEffect(() => {
    (async () => {
      const perm = await requestRecordingPermissionsAsync();
      hasPermission.current = perm.granted;
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
    })();
  }, []);

  // Cuando termina de sonar la respuesta del backend, volvemos a idle
  useEffect(() => {
    if (status === "playing" && playerStatus.didJustFinish) {
      setStatus("idle");
    }
  }, [playerStatus.didJustFinish, status]);

  const startRecording = useCallback(async () => {
    if (!hasPermission.current) {
      const perm = await requestRecordingPermissionsAsync();
      hasPermission.current = perm.granted;
      if (!perm.granted) return;
    }
    await recorder.prepareToRecordAsync();
    recorder.record();
    setStatus("recording");
  }, [recorder]);

  function blobToDataUri(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

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
    // Estado "sending" YA, antes de cualquier await — así el botón
    // refleja el bloqueo al instante, no cuando React decida repintar.
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

    try {
      const responseBlob = await sendVoiceRecording(uri);
      const dataUri = await blobToDataUri(responseBlob);
      player.replace({ uri: dataUri });
      player.play();
      setStatus("playing");
    } catch (err) {
      console.error("Error enviando audio al backend:", err);
      setStatus("idle");
    } finally {
      cleanupFile(uri);
    }
  }, [recorder, player]);

  const interruptPlaybackAndRecord = useCallback(async () => {
    player.pause();
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