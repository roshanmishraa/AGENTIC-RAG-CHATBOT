import { useState } from "react";
import { useStreamingChat } from "../hooks/useStreamingChat";

export default function ChatPage() {
  const [input, setInput] = useState("");
  const [chatId] = useState(() => crypto.randomUUID());
  const { messages, sendMessage, isStreaming } = useStreamingChat(chatId);

  const handleSend = () => {
    if (!input.trim()) return;
    sendMessage(input);
    setInput("");
  };

  return (
    <div className="flex flex-col h-screen max-w-3xl mx-auto p-4">
      <div className="flex-1 overflow-y-auto space-y-4">
        {messages.map((m, i) => (
          <div key={i} className={`p-3 rounded-lg ${m.role === "user" ? "bg-blue-100 ml-auto max-w-md" : "bg-gray-100 max-w-md"}`}>
            <p className="text-sm">{m.content}</p>
            {m.citations && m.citations.length > 0 && (
              <div className="mt-2 text-xs text-gray-500">
                Sources: {m.citations.map((c, idx) => `[${idx + 1}]`).join(" ")}
              </div>
            )}
          </div>
        ))}
        {isStreaming && <div className="text-sm text-gray-400">Thinking...</div>}
      </div>

      <div className="flex gap-2 mt-4">
        <input
          className="flex-1 border rounded-lg px-4 py-2"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Ask a question about your documents..."
        />
        <button onClick={handleSend} disabled={isStreaming} className="bg-blue-600 text-white px-4 py-2 rounded-lg disabled:opacity-50">
          Send
        </button>
      </div>
    </div>
  );
}