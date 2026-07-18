import React, { useState } from "react";
import { View, StyleSheet, TouchableOpacity, Text } from "react-native";
// Tus imports reales corregidos
import TextScreen from "./src/screens/TextScreen";
import VoiceScreen from "./src/screens/VoiceScreen";  

export default function App() {
  const [mode, setMode] = useState('voice'); // 'voice' o 'text'

  return (
    <View style={styles.container}>
      {/* 1. Renderizado condicional de la pantalla activa */}
      {mode === 'voice' ? <VoiceScreen /> : <TextScreen />}
      
      {/* 2. Botón rápido para alternar entre modos */}
      <TouchableOpacity 
        style={styles.toggleButton} 
        onPress={() => setMode(mode === 'voice' ? 'text' : 'voice')}
      >
        <Text style={styles.toggleText}>
          {mode === 'voice' ? "💬 Cambiar a Texto" : "🎙️ Cambiar a Voz"}
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  toggleButton: {
    position: 'absolute',
    top: 50, // Lo sitúa arriba en la pantalla para no molestar abajo
    right: 20,
    backgroundColor: '#007AFF',
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
    elevation: 5,
  },
  toggleText: {
    color: '#fff',
    fontWeight: 'bold',
  },
});