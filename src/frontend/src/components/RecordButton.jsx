import React, { useEffect, useRef, useState } from "react";
import { Animated, Pressable, StyleSheet, View, Image, Easing } from "react-native";
import Svg, { Defs, LinearGradient, Stop, Circle } from "react-native-svg";

const AnimatedView = Animated.createAnimatedComponent(View);
const AnimatedCircle = Animated.createAnimatedComponent(Circle);

export default function VoiceButton() {
  const [active, setActive] = useState(false);

  const rotation = useRef(new Animated.Value(0)).current;
  const pulse = useRef(new Animated.Value(1)).current;
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
          Animated.timing(pulse, {
            toValue: 1.3,
            duration: 1200,
            useNativeDriver: false,
          }),
          Animated.timing(pulse, {
            toValue: 1,
            duration: 1200,
            useNativeDriver: false,
          }),
        ])
      );
      pulseLoopRef.current.start();

      Animated.spring(scale, {
        toValue: 1.3,
        useNativeDriver: true,
      }).start();
    } else {
      cancelled = true;
      rotation.stopAnimation();
      if (pulseLoopRef.current) pulseLoopRef.current.stop();
      pulse.setValue(1);

      Animated.spring(scale, {
        toValue: 1,
        useNativeDriver: true,
      }).start();
    }

    return () => {
      cancelled = true;
      rotation.stopAnimation();
      if (pulseLoopRef.current) pulseLoopRef.current.stop();
    };
  }, [active]);

  const spin = rotation.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "360deg"],
  });

  const pulseRadius = pulse.interpolate({
    inputRange: [1, 1.3],
    outputRange: [69, 100],
  });
  const pulseOpacity = pulse.interpolate({
    inputRange: [1, 1.3],
    outputRange: [0.8, 0], //TODO mirar para cambiar esto y que no desaparezca el pulso. (tb tocar tamaño del svg xq se corta)
  });

  return (
    <Pressable onPress={() => setActive(!active)}>
      <AnimatedView
        style={[
          styles.container,
          {
            transform: [{ scale }],
          },
        ]}
      >
        <Animated.View
          style={{
            transform: [{ rotate: spin }],
          }}
        >
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

            <Circle
              cx="70"
              cy="70"
              r="62"
              stroke="url(#grad)"
              strokeWidth="6"
              fill="transparent"
            />
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

        <View style={styles.core}>
          <Image source={require("../../assets/unicaja.png")} style={styles.image} />
        </View>
      </AnimatedView>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    width: 140,
    height: 140,
    justifyContent: "center",
    alignItems: "center",
  },
  core: {
    position: "absolute",
    width: 100,
    height: 100,
    borderRadius: 50,
    justifyContent: "center",
    alignItems: "center",
  },
  image: {
    width: 100,
    height: 100,
    resizeMode: "contain",
  },
  pulseSvg: {
    position: "absolute",
    width: 200,
    height: 200,
    left: -30,
    top: -30,
  },
});