import { useCallback, useEffect, useRef, useState } from "react";
import { useAuthStore } from "../store/authStore";
import { BASE } from "../api/client";
import type { Citation } from "../types";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  attachmentName?: string;
  attachmentKind?: "image" | "voice";
  needsHumanReview?: boolean;
}

function uid() {
  return crypto.randomUUID();
}

/**
 * Drives one conversation (`chatId`). Text messages use the streaming
 * endpoint (POST /chat/message/stream) exactly as before. Image and
 * voice turns are appended via `appendExchange` from ChatPage, since
 * those go through separate non-streaming endpoints that DO return
 * citations synchronously.
 *
 * NOTE on citations: /chat/message/stream only streams raw answer
 * tokens — citations are computed and persisted server-side but never
 * sent back over the stream, so streamed text replies cannot show
 * sources today. This is a backend gap, not a frontend omission.
 */
export function useStreamingChat(chatId: string, initialMessages: ChatMessage[] = []) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const token = useAuthStore((s) => s.accessToken);
  const chatIdRef = useRef(chatId);

  // Reset local state whenever the active conversation changes.
  useEffect(() => {
    chatIdRef.current = chatId;
    setMessages(initialMessages);
    setError(null);
    setIsStreaming(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatId]);

  const appendExchange = useCallback(
    (userMsg: ChatMessage, assistantMsg: ChatMessage) => {
      setMessages((prev) => [...prev, userMsg, assistantMsg]);
    },
    []
  );

  const sendMessage = useCallback(
    async (query: string, documentIds?: string[]) => {
      setError(null);
      const activeChatId = chatIdRef.current;

      setMessages((prev) => [...prev, { id: uid(), role: "user", content: query }]);
      const assistantId = uid();
      setIsStreaming(true);
      setMessages((prev) => [...prev, { id: assistantId, role: "assistant", content: "" }]);

      try {
        const response = await fetch(`${BASE}/chat/message/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            chat_id: activeChatId,
            query,
            document_ids: documentIds?.length ? documentIds : undefined,
          }),
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          const message = errData?.detail || `Request failed (${response.status})`;
          setMessages((prev) => prev.slice(0, -1));
          setError(message);
          return;
        }

        const reader = response.body?.getReader();
        if (!reader) {
          setMessages((prev) => prev.slice(0, -1));
          setError("Stream unavailable — no response body.");
          return;
        }

        const decoder = new TextDecoder();

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value, { stream: true });

            setMessages((prev) => {
              const updated = [...prev];
              const idx = updated.findIndex((m) => m.id === assistantId);
              if (idx === -1) return prev;
              updated[idx] = { ...updated[idx], content: updated[idx].content + chunk };
              return updated;
            });
          }
        } catch {
          setError("Stream interrupted. Please try again.");
        } finally {
          reader.releaseLock();
        }
      } catch {
        setMessages((prev) => prev.slice(0, -1));
        setError("Network error. Check your connection.");
      } finally {
        setIsStreaming(false);
      }
    },
    [token]
  );

  const clearError = useCallback(() => setError(null), []);

  return { messages, setMessages, sendMessage, appendExchange, isStreaming, error, clearError };
}