import React, { useState, useRef } from "react";
import {
  StyleSheet,
  View,
  TextInput,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  FlatList,
} from "react-native";

import { SafeAreaView } from "react-native-safe-area-context";
import { Send, Square } from "lucide-react-native";
import BubbleText from "../components/BubbleText/BubbleText";

export default function TextScreen() {
  const [text, setText] = useState("");
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const abortControllerRef = useRef(null);
  const flatListRef = useRef(null);

  const handleSendOrCancel = async () => {
    if (isLoading) {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      setIsLoading(false);
      return;
    }

    const trimmedText = text.trim();
    if (!trimmedText) return;

    const userMessage = {
      id: Date.now().toString(),
      sender: "user",
      text: trimmedText,
    };

    setMessages((prev) => [...prev, userMessage]);
    setText("");
    setIsLoading(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await fetch("YOUR_BACKEND_URL/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: trimmedText }),
        signal: controller.signal,
      });

      const data = await response.json();

      const botMessage = {
        id: (Date.now() + 1).toString(),
        sender: "bot",
        text: data.response || data.message || "Sin respuesta",
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch (error) {
      if (error.name === "AbortError") {
        console.log("Petición cancelada por el usuario");
      } else {
        console.error("Error conectando con el backend:", error);
      }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        <View style={styles.innerContainer}>
          {/* Lista de conversación */}
          <FlatList
            ref={flatListRef}
            data={messages}
            keyExtractor={(item) => item.id}
            style={styles.list}
            contentContainerStyle={styles.listContent}
            keyboardShouldPersistTaps="handled"
            onContentSizeChange={() =>
              flatListRef.current?.scrollToEnd({ animated: true })
            }
            renderItem={({ item }) => (
              <BubbleText sender={item.sender} text={item.text} />
            )}
          />

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
                editable={!isLoading}
              />
              <Pressable
                style={({ pressed }) => [
                  styles.sendButton,
                  isLoading && styles.cancelButton,
                  pressed &&
                    (isLoading
                      ? styles.cancelButtonPressed
                      : styles.sendButtonPressed),
                ]}
                onPress={handleSendOrCancel}
              >
                {isLoading ? (
                  <Square size={14} color="#FFFFFF" fill="#FFFFFF" />
                ) : (
                  <Send style={styles.sendIcon} size={17} />
                )}
              </Pressable>
            </View>
          </View>
        </View>
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
  },
  list: {
    flex: 1,
  },
  listContent: {
    flexGrow: 1,
    justifyContent: "flex-end", 
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 8,
  },
  bottomContainer: {
    width: "100%",
    paddingHorizontal: 16,
    paddingBottom: 8,
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
  cancelButton: {
    backgroundColor: "#E53E3E",
  },
  cancelButtonPressed: {
    backgroundColor: "#9B2C2C",
  },
  sendIcon: {
    color: "#FFFFFF",
  },
});