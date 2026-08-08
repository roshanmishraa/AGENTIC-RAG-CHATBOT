import { useState, useCallback } from "react";
import { useAuthStore } from "../store/authStore";
import { BASE } from "../api/client";          // ← Fix 1: BASE import

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: any[];
}

export function useStreamingChat(chatId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const token = useAuthStore((s) => s.accessToken);

  const sendMessage = useCallback(async (query: string) => {
    setError(null);

    // User message add karo
    setMessages((prev) => [...prev, { role: "user", content: query }]);
    setIsStreaming(true);

    // Empty assistant placeholder — chunks isme fill honge
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      const response = await fetch(`${BASE}/chat/message/stream`, {   // ← Fix 1: BASE use karo
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ chat_id: chatId, query }),
      });

      // ── Fix 2: HTTP error check ──────────────────────────
      // Agar backend 401/403/500 return kare toh stream mat karo
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        const message = errData?.detail || `Request failed (${response.status})`;

        // Placeholder assistant message remove karo
        setMessages((prev) => prev.slice(0, -1));
        setError(message);
        return;
      }
      // ────────────────────────────────────────────────────

      const reader = response.body?.getReader();

      // ── Fix 3: Proper reader check ───────────────────────
      if (!reader) {
        setMessages((prev) => prev.slice(0, -1));
        setError("Stream unavailable — no response body.");
        return;
      }
      // ────────────────────────────────────────────────────

      const decoder = new TextDecoder();

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });

          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              content: updated[updated.length - 1].content + chunk,
            };
            return updated;
          });
        }
      } catch (streamErr) {
        // Stream beech mein toot gayi
        setError("Stream interrupted. Please try again.");
      } finally {
        reader.releaseLock();
      }

    } catch (networkErr) {
      // Network error — server unreachable
      setMessages((prev) => prev.slice(0, -1));
      setError("Network error. Check your connection.");
    } finally {
      setIsStreaming(false);
    }
  }, [chatId, token]);

  // Error clear karne ka method — ChatPage se call kar sako
  const clearError = useCallback(() => setError(null), []);

  return { messages, sendMessage, isStreaming, error, clearError };
}