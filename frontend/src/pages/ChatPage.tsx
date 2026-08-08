import { useState, useRef, useEffect } from "react";
import { useStreamingChat } from "../hooks/useStreamingChat";

export default function ChatPage() {
  const [input, setInput] = useState("");
  const [chatId] = useState(() => crypto.randomUUID());
  const { messages, sendMessage, isStreaming, error, clearError } = useStreamingChat(chatId);
  const bottomRef = useRef<HTMLDivElement>(null);

  // ── Auto-scroll jab bhi naya message aaye ─────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim() || isStreaming) return;
    sendMessage(input.trim());
    setInput("");
  };

  return (
    <div className="flex flex-col h-screen max-w-3xl mx-auto p-4">

      {/* ── Messages Area ───────────────────────────────── */}
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">

        {/* Empty state */}
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            Ask a question about your documents to get started.
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={`p-3 rounded-lg max-w-md ${
              m.role === "user"
                ? "bg-blue-100 ml-auto text-right"
                : "bg-gray-100"
            }`}
          >
            {/* Message content */}
            <p className="text-sm whitespace-pre-wrap">{m.content}</p>

            {/* Citations */}
            {m.citations && m.citations.length > 0 && (
              <div className="mt-2 text-xs text-gray-500">
                Sources: {m.citations.map((_, idx) => `[${idx + 1}]`).join(" ")}
              </div>
            )}
          </div>
        ))}

        {/* Streaming indicator */}
        {isStreaming && (
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <span className="animate-pulse">●</span>
            <span>Thinking...</span>
          </div>
        )}

        {/* ── Error message ──────────────────────────────── */}
        {error && (
          <div className="flex items-center justify-between bg-red-50 border border-red-200 text-red-600 text-sm p-3 rounded-lg">
            <span>{error}</span>
            <button
              onClick={clearError}
              className="ml-4 text-red-400 hover:text-red-600 font-bold"
            >
              ✕
            </button>
          </div>
        )}

        {/* Auto-scroll anchor */}
        <div ref={bottomRef} />
      </div>

      {/* ── Input Area ──────────────────────────────────── */}
      <div className="flex gap-2 mt-4 border-t pt-4">
        <input
          className="flex-1 border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
          placeholder="Ask a question about your documents..."
          disabled={isStreaming}
        />
        <button
          onClick={handleSend}
          disabled={isStreaming || !input.trim()}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg disabled:opacity-50 hover:bg-blue-700 transition-colors"
        >
          Send
        </button>
      </div>

    </div>
  );
}