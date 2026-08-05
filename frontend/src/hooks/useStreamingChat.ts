import { useState, useCallback } from "react";
import { useAuthStore } from "../store/authStore";

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: any[];
}

export function useStreamingChat(chatId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const token = useAuthStore((s) => s.accessToken);

  const sendMessage = useCallback(async (query: string) => {
    setMessages((prev) => [...prev, { role: "user", content: query }]);
    setIsStreaming(true);

    // Placeholder assistant message that gets filled in as chunks arrive
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/chat/message/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ chat_id: chatId, query }),
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);

        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1].content += chunk;
          return updated;
        });
      }
    } finally {
      setIsStreaming(false);
    }
  }, [chatId, token]);

  return { messages, sendMessage, isStreaming };
}