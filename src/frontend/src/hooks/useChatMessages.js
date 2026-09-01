import { useCallback, useRef, useState } from "react";
import { sendChatMessage } from "../services/chatApi";

export function useChatMessages() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const abortControllerRef = useRef(null);

  // Contador incremental para los ids de mensaje .
  const idCounterRef = useRef(0);
  const nextId = () => {
    idCounterRef.current += 1;
    return `msg-${idCounterRef.current}`;
  };

  const sendMessage = useCallback(
    async (text) => {
      const trimmed = text.trim();
      if (!trimmed || isLoading) return;

      const userMessage = {
        id: nextId(),
        sender: "user",
        text: trimmed,
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const data = await sendChatMessage(trimmed, controller.signal);
        const botMessage = {
          id: nextId(),
          sender: "bot",
          text: data.response || "Sin respuesta",
        };
        setMessages((prev) => [...prev, botMessage]);
      } catch (err) {
        if (err.name === "AbortError") {
          console.log("Petición cancelada por el usuario");
          // No añadimos ninguna burbuja: el usuario canceló a propósito,
          // no es un error que necesite explicación.
        } else {
          console.error("Error conectando con el backend:", err);
          setMessages((prev) => [
            ...prev,
            {
              id: nextId(),
              sender: "bot",
              text: "No se pudo conectar con el backend. Inténtalo de nuevo.",
            },
          ]);
        }
      } finally {
        setIsLoading(false);
        abortControllerRef.current = null;
      }
    },
    [isLoading]
  );

  const cancelMessage = useCallback(() => {
    abortControllerRef.current?.abort();
  }, []);

  return { messages, isLoading, sendMessage, cancelMessage };
}