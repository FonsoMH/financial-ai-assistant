import React, { useEffect, useRef, useState } from "react";
import { Animated, Pressable, StyleSheet, View, Image, Easing } from "react-native";
import Svg, { Defs, LinearGradient, Stop, Circle, Path } from "react-native-svg";
import { useVoiceRecorder } from "../hooks/useVoiceRecorder";

const AnimatedView = Animated.createAnimatedComponent(View);
const AnimatedCircle = Animated.createAnimatedComponent(Circle);

const WAVE_POINTS = 64;
const WAVE_CENTER = 100;
const WAVE_BASE_RADIUS = 68; 
const WAVE_FREQUENCY = 6; 
const WAVE_SPEED = 1.4; 

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
  d += "Z";
  return d;
}

export default function RecordButton() {
  const { active, isPlaying, toggle } = useVoiceRecorder();

  const rotation = useRef(new Animated.Value(0)).current;
  const pulse = useRef(new Animated.Value(1)).current;
  const scale = useRef(new Animated.Value(1)).current;
  const speak = useRef(new Animated.Value(0)).current; 

  const rotationValueRef = useRef(0);
  const pulseLoopRef = useRef(null);
  const speakLoopActiveRef = useRef(false);
  const speakAmpRef = useRef(0);

  const [wavePath, setWavePath] = useState(null);
  const waveIntervalRef = useRef(null);
  const waveTimeRef = useRef(0);

  useEffect(() => {
    const id = rotation.addListener(({ value }) => {
      rotationValueRef.current = value;
    });
    return () => rotation.removeListener(id);
  }, [rotation]);

  useEffect(() => {
    const id = speak.addListener(({ value }) => {
      speakAmpRef.current = value;
    });
    return () => speak.removeListener(id);
  }, [speak]);

  // --- Animación de grabación (anillo girando + pulso constante) ---
  useEffect(() => {
    let cancelled = false;

    if (active) {
      const spin = () => {
        const from = rotationValueRef.current;
        Animated.timing(rotation, {
          toValue: from + 1,
          duration: 4000,
          easing: Easing.linear,
          useNativeDriver: true,
        }).start(({ finished }) => {
          if (finished && !cancelled) spin();
        });
      };
      spin();

      pulseLoopRef.current = Animated.loop(
        Animated.sequence([
          Animated.timing(pulse, { toValue: 1.3, duration: 1200, useNativeDriver: false }),
          Animated.timing(pulse, { toValue: 1, duration: 1200, useNativeDriver: false }),
        ])
      );
      pulseLoopRef.current.start();

      Animated.spring(scale, { toValue: 1.3, useNativeDriver: true }).start();
    } else {
      cancelled = true;
      rotation.stopAnimation();
      if (pulseLoopRef.current) pulseLoopRef.current.stop();
      pulse.setValue(1);

      Animated.spring(scale, { toValue: 1, useNativeDriver: true }).start();
    }

    return () => {
      cancelled = true;
      rotation.stopAnimation();
      if (pulseLoopRef.current) pulseLoopRef.current.stop();
    };
  }, [active]);

  // --- "Volumen" del habla (sigue alimentando cuánto se aleja la onda del botón) ---
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
  }, [isPlaying]);

  // --- Geometría de la onda: forma fija, solo gira a velocidad constante ---
  useEffect(() => {
    if (isPlaying) {
      waveIntervalRef.current = setInterval(() => {
        waveTimeRef.current += 0.06;
        const amplitude = 14 + speakAmpRef.current * 14; // 8-22px, reacciona al "volumen"
        setWavePath(buildWavePath(waveTimeRef.current, amplitude));
      }, 40); // ~25fps
    } else {
      if (waveIntervalRef.current) clearInterval(waveIntervalRef.current);
      setWavePath(null);
    }

    return () => {
      if (waveIntervalRef.current) clearInterval(waveIntervalRef.current);
    };
  }, [isPlaying]);

  const spin = rotation.interpolate({ inputRange: [0, 1], outputRange: ["0deg", "360deg"] });
  const pulseRadius = pulse.interpolate({ inputRange: [1, 1.3], outputRange: [69, 100] });
  const pulseOpacity = pulse.interpolate({ inputRange: [1, 1.3], outputRange: [0.8, 0] });

  return (
    <Pressable onPress={toggle}>
      <AnimatedView style={[styles.container, { transform: [{ scale }] }]}>
        <Animated.View style={{ transform: [{ rotate: spin }] }}>
          <Svg width={140} height={140}>
            <Defs>
              <LinearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                <Stop offset="0%" stopColor="#29d51f" />
                <Stop offset="20%" stopColor="#29d51f" />
                <Stop offset="40%" stopColor="#FFFFFF" />
                <Stop offset="60%" stopColor="#FFFFFF" />
                <Stop offset="80%" stopColor="#015368" />
                <Stop offset="100%" stopColor="#015368" />
              </LinearGradient>
            </Defs>
            <Circle cx="70" cy="70" r="62" stroke="url(#grad)" strokeWidth="6" fill="transparent" />
          </Svg>
        </Animated.View>

        {active && (
          <Svg width={200} height={200} style={styles.pulseSvg}>
            <AnimatedCircle
              cx={100}
              cy={100}
              r={pulseRadius}
              stroke="#29d51f"
              strokeWidth={3}
              fill="transparent"
              opacity={pulseOpacity}
            />
          </Svg>
        )}

        {isPlaying && wavePath && (
          <Svg width={200} height={200} style={styles.pulseSvg}>
            <Path d={wavePath} stroke="#FFFFFF" strokeWidth={3.5} fill="none" opacity={0.75} /> 
          </Svg>
        )}

        <View style={styles.core}>
          <Image source={require("../../assets/unicaja.png")} style={styles.image} />
        </View>
      </AnimatedView>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { width: 140, height: 140, justifyContent: "center", alignItems: "center" },
  core: { position: "absolute", width: 100, height: 100, borderRadius: 50, justifyContent: "center", alignItems: "center" },
  image: { width: 100, height: 100, resizeMode: "contain" },
  pulseSvg: { position: "absolute", width: 200, height: 200, left: -30, top: -30 },
});