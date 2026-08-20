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

  const stopRecordingAndSend = useCallback(async () => {
    await recorder.stop();
    const uri = recorder.uri;
    if (!uri) {
      setStatus("idle");
      return;
    }
    setStatus("sending");
    try {
      const responseBlob = await sendVoiceRecording(uri);
      const dataUri = await blobToDataUri(responseBlob);
      player.replace({ uri: dataUri });
      player.play();
      setStatus("playing");
      cleanupFile(uri);
    } catch (err) {
      console.error("Error enviando audio al backend:", err);
      setStatus("idle");
      cleanupFile(uri);
    }
  }, [recorder, player]);

  const interruptPlaybackAndRecord = useCallback(async () => {
    player.pause();
    await startRecording();
  }, [player, startRecording]);


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

  const toggle = useCallback(async () => {
    switch (status) {
      case "idle":
        return startRecording();
      case "recording":
        return stopRecordingAndSend();
      case "playing":
        return interruptPlaybackAndRecord();
      case "sending":
        return; // ignoramos toques mientras esperamos al backend
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