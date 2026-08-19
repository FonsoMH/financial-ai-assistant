// hooks/useVoiceRecorder.js
import { useEffect, useRef, useState } from "react";
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

// Antes el modo de audio se cambiaba entre "grabación" y "reproducción" en
// CADA turno, con una espera fija de 500ms para dejar que el cambio de
// sesión se asentara a nivel de SO (AVAudioSession en iOS). Ese coste se
// pagaba en cada mensaje de la conversación — era la causa real de la
// lentitud, no un bug puntual.
//
// El modo "grabación" permite reproducir audio igualmente, así que fijamos
// el modo de audio UNA sola vez al montar el hook y no lo tocamos más.
async function configureAudioModeOnce() {
  try {
    await setAudioModeAsync({
      playsInSilentMode: true,
      allowsRecording: true,
    });
  } catch (err) {
    console.log("ERROR configurando el modo de audio:", err);
  }
}

const STATUS = {
  IDLE: "idle",
  RECORDING: "recording",
  SENDING: "sending",
  PLAYING: "playing",
};

export function useVoiceRecorder() {
  const [status, setStatusState] = useState(STATUS.IDLE);

  // Espejo en ref del estado: lo necesitamos porque toggle() y los
  // callbacks async leen el estado "actual" en un momento arbitrario, y
  // una closure de useState quedaría desactualizada (stale) entre
  // renders. Es la ÚNICA pieza de estado "extra" que necesitamos, frente
  // a las tres del hook anterior.
  const statusRef = useRef(STATUS.IDLE);
  const setStatus = (next) => {
    statusRef.current = next;
    setStatusState(next);
  };

  const audioRecorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const playerRef = useRef(null);

  // Identifica el turno actual (grabar -> enviar -> reproducir). Cualquier
  // callback async que llegue tarde (respuesta de red, evento del
  // reproductor) compara su id contra este antes de tocar estado; si no
  // coincide, el turno ya fue interrumpido y se ignora sin más.
  const turnIdRef = useRef(0);

  useEffect(() => {
    configureAudioModeOnce();
  }, []);

  function releasePlayer() {
    const player = playerRef.current;
    playerRef.current = null;
    if (!player) return;
    try { player.pause(); } catch (err) { console.log("Error al pausar el player:", err); }
    try { player.remove(); } catch (err) { console.log("Error al hacer remove() del player:", err); }
    try { player.release(); } catch (err) { console.log("Error al hacer release() del player:", err); }
  }

  function cleanupFile(uri) {
    try {
      const file = new File(uri);
      if (file.exists) file.delete();
    } catch (err) {
      console.log("No se pudo borrar el archivo temporal:", err);
    }
  }

  async function startRecording() {
    const myTurn = ++turnIdRef.current;
    releasePlayer();

    const permission = await AudioModule.requestRecordingPermissionsAsync();
    if (!permission.granted) {
      Alert.alert("Permiso denegado", "Necesito acceso al micrófono para grabar.");
      if (myTurn === turnIdRef.current) setStatus(STATUS.IDLE);
      return;
    }

    try {
      await audioRecorder.prepareToRecordAsync();
      audioRecorder.record();
    } catch (err) {
      console.log("ERROR en startRecording:", err);
      if (myTurn === turnIdRef.current) {
        Alert.alert("Error", "No se pudo iniciar la grabación.");
        setStatus(STATUS.IDLE);
      }
      return;
    }

    if (myTurn === turnIdRef.current) setStatus(STATUS.RECORDING);
  }

  async function stopRecordingAndSend() {
    const myTurn = turnIdRef.current;
    setStatus(STATUS.SENDING);

    let uri;
    try {
      await audioRecorder.stop();
      uri = audioRecorder.uri;
    } catch (err) {
      console.log("ERROR al parar la grabación:", err);
      if (myTurn === turnIdRef.current) setStatus(STATUS.IDLE);
      return;
    }

    if (!uri) {
      console.log("⚠️ No hay URI de grabación");
      if (myTurn === turnIdRef.current) setStatus(STATUS.IDLE);
      return;
    }

    // Defensivo: si el fichero no existe o está vacío, no llamamos al
    // backend (fallaría con un "Network request failed" engañoso).
    try {
      const file = new File(uri);
      if (!file.exists || file.size === 0) {
        console.log(`⚠️ Grabación inválida (exists=${file.exists}, size=${file.size}) en ${uri}`);
        Alert.alert("Grabación vacía", "No se ha podido grabar audio, inténtalo de nuevo.");
        cleanupFile(uri);
        if (myTurn === turnIdRef.current) setStatus(STATUS.IDLE);
        return;
      }
    } catch (err) {
      console.log("ERROR comprobando el fichero de audio:", err);
      Alert.alert("Grabación vacía", "No se ha podido grabar audio, inténtalo de nuevo.");
      cleanupFile(uri);
      if (myTurn === turnIdRef.current) setStatus(STATUS.IDLE);
      return;
    }

    let blob;
    try {
      blob = await sendVoiceRecording(uri);
    } catch (err) {
      cleanupFile(uri);
      if (myTurn === turnIdRef.current) {
        const message = err.name === "AbortError"
          ? "El backend no respondió a tiempo."
          : "No se pudo conectar con el backend.";
        Alert.alert("Error", message);
        setStatus(STATUS.IDLE);
      }
      console.log("ERROR al enviar el audio al backend:", err);
      return;
    }
    cleanupFile(uri);

    // Si mientras se enviaba el usuario ya interrumpió (nuevo turno en
    // marcha), no seguimos: esta respuesta ya es obsoleta.
    if (myTurn !== turnIdRef.current) return;

    try {
      await playAudioBlob(blob, myTurn);
    } catch (err) {
      console.log("ERROR al reproducir el audio:", err);
      if (myTurn === turnIdRef.current) setStatus(STATUS.IDLE);
    }
  }

  function playAudioBlob(blob, myTurn) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        if (myTurn !== turnIdRef.current) { resolve(); return; }

        try {
          const player = createAudioPlayer({ uri: reader.result });
          playerRef.current = player;

          player.addListener("playbackStatusUpdate", (playerStatus) => {
            if (myTurn !== turnIdRef.current) return;
            if (playerStatus.didJustFinish) {
              setStatus(STATUS.IDLE);
            }
          });

          player.play();
          setStatus(STATUS.PLAYING);
          resolve();
        } catch (err) {
          reject(err);
        }
      };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  async function toggle() {
    switch (statusRef.current) {
      case STATUS.IDLE:
        await startRecording();
        break;

      case STATUS.RECORDING:
        await stopRecordingAndSend();
        break;

      case STATUS.PLAYING:
        // Barge-in: cortar la reproducción en curso y ponerse a grabar.
        turnIdRef.current++; // invalida el turno de reproducción actual
        releasePlayer();
        await startRecording();
        break;

      case STATUS.SENDING:
        // Ya hay una petición en curso: ignoramos el toque en vez de
        // necesitar un busyRef aparte para protegernos de dobles pulsos.
        break;
    }
  }

  return {
    status,
    active: status === STATUS.RECORDING,
    isPlaying: status === STATUS.PLAYING,
    isSending: status === STATUS.SENDING,
    toggle,
  };
}