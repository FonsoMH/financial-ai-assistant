import { View, StyleSheet } from "react-native";
import VoiceButton from "../components/RecordButton";

export default function VoiceScreen() {
  return (
    <View style={styles.container}>
      <VoiceButton />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0B0F14",
    justifyContent: "center",
    alignItems: "center",
  },
});