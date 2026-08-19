// hooks/useRecordButtonAnimation.js
import { useEffect, useRef } from "react";
import { Animated, Easing } from "react-native";

const SPIN_DURATION_MS = 4000;
const PULSE_MIN = 1;
const PULSE_MAX = 1.3;
const PULSE_HALF_DURATION_MS = 1200;
const ACTIVE_SCALE = 1.3;

/**
 * Animación visual del botón mientras se está grabando: anillo girando a
 * velocidad constante, pulso expansivo en bucle, y un ligero escalado.
 * No sabe nada de grabación/reproducción: solo recibe `active` (boolean).
 */
export function useRecordButtonAnimation(active) {
  const rotation = useRef(new Animated.Value(0)).current;
  const pulse = useRef(new Animated.Value(PULSE_MIN)).current;
  const scale = useRef(new Animated.Value(1)).current;

  const rotationValueRef = useRef(0);
  const pulseLoopRef = useRef(null);

  useEffect(() => {
    const id = rotation.addListener(({ value }) => {
      rotationValueRef.current = value;
    });
    return () => rotation.removeListener(id);
  }, [rotation]);

  useEffect(() => {
    let cancelled = false;

    if (active) {
      const spin = () => {
        const from = rotationValueRef.current;
        Animated.timing(rotation, {
          toValue: from + 1,
          duration: SPIN_DURATION_MS,
          easing: Easing.linear,
          useNativeDriver: true,
        }).start(({ finished }) => {
          if (finished && !cancelled) spin();
        });
      };
      spin();

      pulseLoopRef.current = Animated.loop(
        Animated.sequence([
          Animated.timing(pulse, { toValue: PULSE_MAX, duration: PULSE_HALF_DURATION_MS, useNativeDriver: false }),
          Animated.timing(pulse, { toValue: PULSE_MIN, duration: PULSE_HALF_DURATION_MS, useNativeDriver: false }),
        ])
      );
      pulseLoopRef.current.start();

      Animated.spring(scale, { toValue: ACTIVE_SCALE, useNativeDriver: true }).start();
    } else {
      cancelled = true;
      rotation.stopAnimation();
      pulseLoopRef.current?.stop();
      pulse.setValue(PULSE_MIN);
      Animated.spring(scale, { toValue: 1, useNativeDriver: true }).start();
    }

    return () => {
      cancelled = true;
      rotation.stopAnimation();
      pulseLoopRef.current?.stop();
    };
  }, [active, rotation, pulse, scale]);

  return {
    scale,
    spin: rotation.interpolate({ inputRange: [0, 1], outputRange: ["0deg", "360deg"] }),
    pulseRadius: pulse.interpolate({ inputRange: [PULSE_MIN, PULSE_MAX], outputRange: [69, 100] }),
    pulseOpacity: pulse.interpolate({ inputRange: [PULSE_MIN, PULSE_MAX], outputRange: [0.8, 0] }),
  };
}