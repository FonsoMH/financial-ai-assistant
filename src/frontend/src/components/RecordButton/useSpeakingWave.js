// hooks/useSpeakingWave.js
import { useEffect, useRef, useState } from "react";
import { Animated, Easing } from "react-native";

const WAVE_POINTS = 64;
const WAVE_CENTER = 100;
const WAVE_BASE_RADIUS = 68;
const WAVE_FREQUENCY = 6;
const WAVE_SPEED = 1.4;
const WAVE_MIN_AMPLITUDE = 14;
const WAVE_AMPLITUDE_RANGE = 14;
const WAVE_FRAME_INTERVAL_MS = 40; // ~25fps

function buildWavePath(time, amplitude) {
  const points = [];
  for (let i = 0; i <= WAVE_POINTS; i++) {
    const angle = (i / WAVE_POINTS) * Math.PI * 2;
    const wave = Math.sin(angle * WAVE_FREQUENCY + time * WAVE_SPEED);
    const normalized = (wave + 1) / 2; // [-1,1] → [0,1], siempre hacia fuera
    const r = WAVE_BASE_RADIUS + amplitude * normalized;
    points.push({
      x: WAVE_CENTER + r * Math.cos(angle),
      y: WAVE_CENTER + r * Math.sin(angle),
    });
  }

  let d = `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)} `;
  for (let i = 1; i < points.length; i++) {
    d += `L ${points[i].x.toFixed(1)} ${points[i].y.toFixed(1)} `;
  }
  return d + "Z";
}

/**
 * Onda que se aleja del botón simulando el "volumen" del habla mientras
 * se reproduce audio. No sabe nada de grabación/red: solo recibe
 * `isPlaying` (boolean) y devuelve el `d` del <Path> a dibujar (o null).
 */
export function useSpeakingWave(isPlaying) {
  const speak = useRef(new Animated.Value(0)).current;
  const speakAmpRef = useRef(0);
  const speakLoopActiveRef = useRef(false);

  const [wavePath, setWavePath] = useState(null);
  const waveTimeRef = useRef(0);
  const frameRef = useRef(null);
  const lastFrameTimeRef = useRef(0);

  useEffect(() => {
    const id = speak.addListener(({ value }) => {
      speakAmpRef.current = value;
    });
    return () => speak.removeListener(id);
  }, [speak]);

  // "Volumen" simulado: pequeños picos aleatorios mientras se reproduce.
  useEffect(() => {
    if (isPlaying) {
      speakLoopActiveRef.current = true;

      const randomBeat = () => {
        if (!speakLoopActiveRef.current) return;

        const toValue = 0.3 + Math.random() * 0.7;
        const duration = 120 + Math.random() * 180;

        Animated.timing(speak, {
          toValue,
          duration,
          easing: Easing.out(Easing.quad),
          useNativeDriver: false,
        }).start(() => {
          if (!speakLoopActiveRef.current) return;
          Animated.timing(speak, {
            toValue: 0.15 + Math.random() * 0.15,
            duration: duration * 0.8,
            easing: Easing.in(Easing.quad),
            useNativeDriver: false,
          }).start(({ finished }) => {
            if (finished && speakLoopActiveRef.current) randomBeat();
          });
        });
      };

      randomBeat();
    } else {
      speakLoopActiveRef.current = false;
      Animated.timing(speak, { toValue: 0, duration: 200, useNativeDriver: false }).start();
    }

    return () => {
      speakLoopActiveRef.current = false;
    };
  }, [isPlaying, speak]);

  // Geometría de la onda, con requestAnimationFrame en vez de setInterval:
  // se sincroniza con el refresco de pantalla y se pausa sola si la app
  // pasa a background, en vez de seguir disparando un timer a ciegas.
  useEffect(() => {
    if (isPlaying) {
      lastFrameTimeRef.current = 0;

      const tick = (now) => {
        if (!lastFrameTimeRef.current) lastFrameTimeRef.current = now;
        const delta = now - lastFrameTimeRef.current;

        if (delta >= WAVE_FRAME_INTERVAL_MS) {
          waveTimeRef.current += 0.06;
          const amplitude = WAVE_MIN_AMPLITUDE + speakAmpRef.current * WAVE_AMPLITUDE_RANGE;
          setWavePath(buildWavePath(waveTimeRef.current, amplitude));
          lastFrameTimeRef.current = now;
        }

        frameRef.current = requestAnimationFrame(tick);
      };

      frameRef.current = requestAnimationFrame(tick);
    } else {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      setWavePath(null);
    }

    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [isPlaying]);

  return wavePath;
}