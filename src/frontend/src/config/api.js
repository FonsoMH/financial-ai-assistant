import Constants from 'expo-constants';

/**
 * Obtiene dinámicamente la IP del host donde corre el bundler de Expo.
 * Esto permite que cualquier persona clone el repo y la app detecte 
 * automáticamente la IP de su PC en la red local.
 */
const getBaseUrl = () => {
  const hostUri = Constants.expoConfig?.hostUri;
  
  if (hostUri) {
    const ip = hostUri.split(':')[0];
    return `http://${ip}:8000`;
  }

  return 'http://localhost:8000';
};

export const API_BASE_URL = getBaseUrl();
export const VOICE_ENDPOINT = `${API_BASE_URL}/api/voice`;
export const WS_VOICE_ENDPOINT = `${API_BASE_URL.replace(/^http/, "ws")}/ws/voice`;
export const CHAT_ENDPOINT = `${API_BASE_URL}/api/chat`;
