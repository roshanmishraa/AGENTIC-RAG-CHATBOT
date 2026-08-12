import { useCallback, useEffect, useState } from "react";
import type { ChatMessage } from "./useStreamingChat";

export interface ConversationMeta {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
}

interface StoredConversation extends ConversationMeta {
  messages: ChatMessage[];
}

function storageKey(userId: string) {
  return `conversations:${userId}`;
}

function loadAll(userId: string): StoredConversation[] {
  try {
    const raw = localStorage.getItem(storageKey(userId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveAll(userId: string, convos: StoredConversation[]) {
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(convos));
  } catch {
    // storage full or unavailable — conversation history simply won't persist
  }
}

function titleFromQuery(query: string) {
  const trimmed = query.trim().replace(/\s+/g, " ");
  return trimmed.length > 48 ? `${trimmed.slice(0, 48)}…` : trimmed || "New chat";
}

/**
 * Conversation history is stored entirely in the browser (localStorage).
 * The backend has no endpoint to list a user's chats or fetch a chat's
 * past messages (only POST /chat/message*), so this sidebar can only
 * remember what happened in this browser — it will not sync across
 * devices or survive clearing site data. That is a backend gap, not
 * something this UI can safely fake.
 */
export function useConversations(userId: string | undefined) {
  const [conversations, setConversations] = useState<ConversationMeta[]>([]);

  useEffect(() => {
    if (!userId) {
      setConversations([]);
      return;
    }
    const all = loadAll(userId);
    all.sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1));
    setConversations(all.map(({ id, title, createdAt, updatedAt }) => ({ id, title, createdAt, updatedAt })));
  }, [userId]);

  const getMessages = useCallback(
    (chatId: string): ChatMessage[] => {
      if (!userId) return [];
      const found = loadAll(userId).find((c) => c.id === chatId);
      return found?.messages ?? [];
    },
    [userId]
  );

  const upsert = useCallback(
    (chatId: string, messages: ChatMessage[], seedTitle?: string) => {
      if (!userId) return;
      const all = loadAll(userId);
      const now = new Date().toISOString();
      const idx = all.findIndex((c) => c.id === chatId);

      if (idx === -1) {
        all.push({
          id: chatId,
          title: seedTitle ? titleFromQuery(seedTitle) : "New chat",
          createdAt: now,
          updatedAt: now,
          messages,
        });
      } else {
        all[idx] = { ...all[idx], messages, updatedAt: now };
      }

      saveAll(userId, all);
      const meta = all
        .map(({ id, title, createdAt, updatedAt }) => ({ id, title, createdAt, updatedAt }))
        .sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1));
      setConversations(meta);
    },
    [userId]
  );

  const remove = useCallback(
    (chatId: string) => {
      if (!userId) return;
      const all = loadAll(userId).filter((c) => c.id !== chatId);
      saveAll(userId, all);
      setConversations(all.map(({ id, title, createdAt, updatedAt }) => ({ id, title, createdAt, updatedAt })));
    },
    [userId]
  );

  return { conversations, getMessages, upsert, remove };
}