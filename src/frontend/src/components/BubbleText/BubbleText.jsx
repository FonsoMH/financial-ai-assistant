import React from "react";
import { View, StyleSheet, Text } from "react-native";

export default function BubbleText({ sender, text }) {
    return (
      <View style={sender === "user" ? styles.userBubble : styles.botBubble}>
        <Text style={styles.content}>{text}</Text>
      </View>
    );
}

const styles = StyleSheet.create({
  content: { 
    color: "#FFFFFF", 
    fontSize: 16, 
    textAlign: "left", 
    paddingHorizontal: 14, 
    paddingVertical: 10 
  },
  userBubble: { 
    alignSelf: "flex-end", 
    maxWidth: "80%", 
    justifyContent: "center", 
    backgroundColor: "#1773e3", 
    borderRadius: 20, 
    borderWidth: 2, 
    borderColor: "#29d51f",
    marginVertical: 5
  },
  botBubble: { 
    alignSelf: "flex-start", 
    maxWidth: "80%", 
    justifyContent: "center", 
    backgroundColor: "#29d51f", 
    borderRadius: 20, 
    borderWidth: 2, 
    borderColor: "#1773e3",
    marginVertical: 5
  },
});
