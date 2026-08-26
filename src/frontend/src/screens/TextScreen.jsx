import { useState } from "react";
import {
  StyleSheet,
  Text,
  TextInput,
  View,
  KeyboardAvoidingView,
  Platform,
  TouchableWithoutFeedback,
  Keyboard,
  Pressable,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Send } from "lucide-react-native";

export default function TextScreen() {
  const [text, setText] = useState("");

  const handleSend = () => {
    if (!text.trim()) return;
    console.log("Mensaje enviado:", text);
    setText("");
  };

  return (
    // edges evita que la zona segura empuje el contenido desde abajo
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        <TouchableWithoutFeedback onPress={Keyboard.dismiss}>
          <View style={styles.innerContainer}>
            {/* Área reservada para la lista de mensajes */}
            <View style={styles.content}>
              <Text style={styles.textMessage}>HOLA SOY TEXTO</Text>
            </View>

            {/* Contenedor inferior con campo de texto y botón */}
            <View style={styles.bottomContainer}>
              <View style={styles.inputWrapper}>
                <TextInput
                  style={styles.insertText}
                  placeholder="Escribe aquí..."
                  placeholderTextColor="#8B949E"
                  value={text}
                  onChangeText={setText}
                  multiline={true}
                />
                <Pressable
                  style={({ pressed }) => [
                    styles.sendButton,
                    pressed && styles.sendButtonPressed,
                  ]}
                  onPress={handleSend}
                >
                  <Send color="#FFFFFF" size={16} />
                </Pressable>
              </View>
            </View>
          </View>
        </TouchableWithoutFeedback>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0B0F14",
  },
  innerContainer: {
    flex: 1,
    justifyContent: "space-between", 
  },
  content: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  bottomContainer: {
    width: "100%",
    paddingHorizontal: 16,
    paddingBottom: 4, 
  },
  inputWrapper: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#161B22",
    borderColor: "#015368",
    borderWidth: 1,
    borderRadius: 25,
    paddingHorizontal: 12,
    paddingVertical: 6,
    minHeight: 50,
    maxHeight: 120,
  },
  insertText: {
    flex: 1,
    color: "#FFFFFF",
    fontSize: 16,
    paddingRight: 8,
    maxHeight: 100,
  },
  sendButton: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: "#29d51f",
    justifyContent: "center",
    alignItems: "center",
  },
  sendButtonPressed: {
    backgroundColor: "#015368",
  },
  textMessage: {
    color: "#007AFF",
    fontSize: 18,
    fontWeight: "bold",
  },
});