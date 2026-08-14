// hooks/useVoiceRecorder.js
import { useRef, useState } from "react";
import { Alert } from "react-native";
import {
  useAudioRecorder,
  AudioModule,
  RecordingPresets,
  setAudioModeAsync,
  createAudioPlayer,
} from "expo-audio";
import { File } from "expo-file-system";
import { sendVoiceRecording } from "../services/voiceApi";

export function useVoiceRecorder() {
  const [active, setActive] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);

  const playerRef = useRef(null);
  const audioRecorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);

  async function startRecording() {
    try {
      const status = await AudioModule.requestRecordingPermissionsAsync();
      if (!status.granted) {
        Alert.alert("Permiso denegado", "Necesito acceso al micrófono para grabar.");
        return;
      }

      await setAudioModeAsync({
        playsInSilentMode: true,
        allowsRecording: true,
      });

      await audioRecorder.prepareToRecordAsync();
      audioRecorder.record();
      setActive(true);
    } catch (err) {
      console.log("ERROR en startRecording:", err);
      Alert.alert("Error", "No se pudo iniciar la grabación.");
    }
  }

  async function stopRecordingAndSend() {
    setActive(false);

    let uri;
    try {
      await audioRecorder.stop();
      uri = audioRecorder.uri;
    } catch (err) {
      console.log("ERROR al parar la grabación:", err);
      return;
    }

    if (!uri) {
      console.log("⚠️ No hay URI de grabación");
      return;
    }

    setIsSending(true);
    try {
      const blob = await sendVoiceRecording(uri);
      await playAudioBlob(blob);
    } catch (err) {
      const message =
        err.name === "AbortError"
          ? "El backend no respondió a tiempo."
          : "No se pudo conectar con el backend.";
      Alert.alert("Error", message);
      console.log("ERROR al enviar el audio al backend:", err);
    } finally {
      setIsSending(false);
      cleanupFile(uri);
    }
  }

  async function playAudioBlob(blob) {
    await setAudioModeAsync({
      playsInSilentMode: true,
      allowsRecording: false,
    });

    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        try {
          if (playerRef.current) {
            playerRef.current.remove();
            playerRef.current.release();
          }

          const player = createAudioPlayer({ uri: reader.result });
          playerRef.current = player;

          player.addListener("playbackStatusUpdate", (status) => {
            setIsPlaying(status.playing);
            if (status.didJustFinish) {
              setIsPlaying(false);
            }
          });

          player.play();
          resolve();
        } catch (err) {
          reject(err);
        }
      };
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


  function stopPlayback() {
    if (playerRef.current) {
        try {
        playerRef.current.pause();
        } catch (err) {
        console.log("Error al parar la reproducción:", err);
        }
    }
    setIsPlaying(false);
  }


  function toggle() {
    if (isSending) return;
    if (isPlaying) {
        stopPlayback();
        startRecording();
        return;
    }
    if (active) {
      stopRecordingAndSend();
    } else {
      startRecording();
    }
  }

  return { active, isSending, isPlaying, toggle };
}