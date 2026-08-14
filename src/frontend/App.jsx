import React, { useState } from "react";
import { View, StyleSheet, TouchableOpacity, Text } from "react-native";
import { useAssets } from 'expo-asset'; // herramienta de caché

import TextScreen from "./src/screens/TextScreen";
import VoiceScreen from "./src/screens/VoiceScreen";  

export default function App() {
  const [mode, setMode] = useState('voice'); // 'voice' o 'text'

  const [assets, error] = useAssets([require("./assets/unicaja.png")]);

  if (!assets && !error) {
    return <View style={[styles.container, { backgroundColor: '#0B0F14' }]} />;
  }


  return (
    <View style={styles.container}>
      {/*Renderizado condicional*/}
      {mode == 'voice' ? <VoiceScreen /> : <TextScreen />}
      
      {/* 2. Botón rápido alternar entre modos TODO   VOLVERLO COMPONENTE*/}
      <TouchableOpacity 
        style={styles.toggleButton} 
        onPress={() => setMode(mode == 'voice' ? 'text' : 'voice')}
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