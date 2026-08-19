import React from "react";
import { Animated, Pressable, StyleSheet, View, Image } from "react-native";
import Svg, { Defs, LinearGradient, Stop, Circle, Path } from "react-native-svg";
import { useVoiceRecorder } from "../../hooks/useVoiceRecorder";
import { useRecordButtonAnimation } from "./useRecordButtonAnimation";
import { useSpeakingWave } from "./useSpeakingWave";

const AnimatedView = Animated.createAnimatedComponent(View);
const AnimatedCircle = Animated.createAnimatedComponent(Circle);

export default function RecordButton() {
  const { active, isPlaying, toggle } = useVoiceRecorder();

  const { scale, spin, pulseRadius, pulseOpacity } = useRecordButtonAnimation(active);
  const wavePath = useSpeakingWave(isPlaying);

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
          <Image source={require("../../../assets/unicaja.png")} style={styles.image} />
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