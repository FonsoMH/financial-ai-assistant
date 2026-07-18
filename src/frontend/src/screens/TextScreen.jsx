import { View, StyleSheet, Text } from "react-native";

export default function TextScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.textMessage}> HOLA SOY TEXTO</Text>
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
  textMessage: {
    color: "#007AFF", 
    fontSize: 18,
    fontWeight: "bold",
  },
});