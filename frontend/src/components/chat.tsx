import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import clsx from "clsx";
import {
  ChevronDown,
  FileText,
  ImageIcon,
  Loader2,
  LogOut,
  Mic,
  Paperclip,
  Plus,
  Search,
  Send,
  Settings,
  Square,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  Volume2,
  X,
} from "lucide-react";
import type { ChatMessage } from "../hooks/useStreamingChat";
import type { AuthUser } from "../store/authStore";
import type { Citation, Document as RagDocument } from "../types";
import { Avatar, Button, EmptyState, Field, IconButton, Input, Modal, StatusBadge, Tooltip, useToast } from "./ui";
import type { ConversationMeta } from "../hooks/useConversations";
import { usersAPI } from "../api/client";

/* ────────────────────────────────────────────────────────────
   Sidebar — conversation history (client-side, see useConversations)
──────────────────────────────────────────────────────────── */
function groupByRecency(conversations: ConversationMeta[]) {
  const now = new Date();
  const today: ConversationMeta[] = [];
  const yesterday: ConversationMeta[] = [];
  const last7: ConversationMeta[] = [];
  const older: ConversationMeta[] = [];

  for (const c of conversations) {
    const d = new Date(c.updatedAt);
    const diffDays = Math.floor((now.getTime() - d.getTime()) / 86400000);
    if (diffDays <= 0) today.push(c);
    else if (diffDays === 1) yesterday.push(c);
    else if (diffDays <= 7) last7.push(c);
    else older.push(c);
  }
  return [
    { label: "Today", items: today },
    { label: "Yesterday", items: yesterday },
    { label: "Previous 7 days", items: last7 },
    { label: "Older", items: older },
  ].filter((g) => g.items.length > 0);
}

export function Sidebar({
  open,
  onClose,
  collapsed,
  onToggleCollapsed,
  conversations,
  activeChatId,
  onSelectConversation,
  onNewChat,
  onDeleteConversation,
  user,
  onOpenSettings,
  onOpenDocuments,
  onOpenAdmin,
  onLogout,
}: {
  open: boolean;
  onClose: () => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  conversations: ConversationMeta[];
  activeChatId: string;
  onSelectConversation: (id: string) => void;
  onNewChat: () => void;
  onDeleteConversation: (id: string) => void;
  user: AuthUser | null;
  onOpenSettings: () => void;
  onOpenDocuments: () => void;
  onOpenAdmin?: () => void;
  onLogout: () => void;
}) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(
    () =>
      query.trim()
        ? conversations.filter((c) => c.title.toLowerCase().includes(query.trim().toLowerCase()))
        : conversations,
    [conversations, query]
  );
  const groups = groupByRecency(filtered);

  const content = (
    <div className="flex flex-col h-full bg-elevated border-r border-border w-[272px]">
      {/* Brand */}
      <div className="flex items-center justify-between px-3.5 h-14 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <div className="h-7 w-7 rounded-md bg-accent flex items-center justify-center text-white text-xs font-bold shrink-0">
            A
          </div>
          <span className="text-sm font-semibold text-primary truncate">Agentic RAG</span>
        </div>
        <IconButton label="Close sidebar" onClick={onClose} className="md:hidden">
          <X size={16} />
        </IconButton>
      </div>

      <div className="px-3 pb-3 space-y-2 shrink-0">
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-2 rounded-lg border border-border bg-card hover:bg-hover px-3 h-10 text-sm font-medium text-primary transition-colors"
        >
          <Plus size={16} />
          New chat
        </button>

        <button
          onClick={onOpenDocuments}
          className="w-full flex items-center gap-2 rounded-lg px-3 h-9 text-sm text-secondary hover:text-primary hover:bg-hover transition-colors"
        >
          <FileText size={15} />
          Documents
        </button>

        {conversations.length > 3 && (
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search conversations"
              className="w-full h-8 rounded-md bg-card border border-border pl-8 pr-2 text-xs text-primary placeholder:text-muted outline-none focus:border-accent"
            />
          </div>
        )}
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto px-2 space-y-3 pb-2">
        {groups.length === 0 ? (
          <p className="px-2 text-xs text-muted">
            {conversations.length === 0 ? "No conversations yet" : "No matches"}
          </p>
        ) : (
          groups.map((group) => (
            <div key={group.label}>
              <p className="px-2 mb-1 text-[11px] font-medium uppercase tracking-wide text-muted">
                {group.label}
              </p>
              <div className="space-y-0.5">
                {group.items.map((c) => (
                  <div
                    key={c.id}
                    className={clsx(
                      "group flex items-center gap-1.5 rounded-lg px-2.5 h-9 cursor-pointer transition-colors",
                      c.id === activeChatId ? "bg-[var(--accent-muted)] text-accent" : "text-secondary hover:bg-hover hover:text-primary"
                    )}
                    onClick={() => onSelectConversation(c.id)}
                  >
                    <span className="flex-1 min-w-0 truncate text-sm">{c.title}</span>
                    <button
                      aria-label="Delete conversation"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteConversation(c.id);
                      }}
                      className="opacity-0 group-hover:opacity-100 text-muted hover:text-[var(--danger)] transition-opacity"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Profile / settings / logout */}
      <div className="shrink-0 border-t border-border p-2 space-y-0.5">
        {user?.role === "admin" && onOpenAdmin && (
          <button
            onClick={onOpenAdmin}
            className="w-full flex items-center gap-2.5 rounded-lg px-2.5 h-9 text-sm text-secondary hover:text-primary hover:bg-hover transition-colors"
          >
            <Settings size={15} />
            Admin dashboard
          </button>
        )}
        <button
          onClick={onOpenSettings}
          className="w-full flex items-center gap-2.5 rounded-lg px-2.5 h-11 hover:bg-hover transition-colors text-left"
        >
          <Avatar name={user?.username || user?.email || "?"} size={28} />
          <span className="flex-1 min-w-0">
            <span className="block text-sm text-primary truncate">{user?.username || user?.email}</span>
            <span className="block text-[11px] text-muted truncate">{user?.email}</span>
          </span>
        </button>
        <button
          onClick={onLogout}
          className="w-full flex items-center gap-2.5 rounded-lg px-2.5 h-9 text-sm text-secondary hover:text-[var(--danger)] hover:bg-hover transition-colors"
        >
          <LogOut size={15} />
          Log out
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop */}
      <div className={clsx("hidden md:block shrink-0 transition-all overflow-hidden", collapsed ? "w-0" : "w-[272px]")}>
        {content}
      </div>
      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={onClose} />
          <div className="absolute inset-y-0 left-0 animate-fadeIn">{content}</div>
        </div>
      )}
    </>
  );
}

/* ────────────────────────────────────────────────────────────
   Citations
──────────────────────────────────────────────────────────── */
export function CitationList({
  citations,
  documentsById,
}: {
  citations: Citation[];
  documentsById: Record<string, RagDocument>;
}) {
  const [expanded, setExpanded] = useState(false);
  if (!citations || citations.length === 0) return null;

  return (
    <div className="mt-2.5 border border-border rounded-lg overflow-hidden bg-elevated/60">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium text-secondary hover:text-primary transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <FileText size={13} />
          Sources ({citations.length})
        </span>
        <ChevronDown size={14} className={clsx("transition-transform", expanded && "rotate-180")} />
      </button>
      {expanded && (
        <div className="border-t border-border divide-y divide-border">
          {citations.map((c, i) => {
            const doc = documentsById[c.document_id];
            return (
              <div key={`${c.document_id}-${c.chunk_index}-${i}`} className="flex items-center gap-2.5 px-3 py-2 text-xs">
                <FileText size={13} className="text-muted shrink-0" />
                <span className="flex-1 min-w-0 truncate text-secondary">
                  {doc?.filename ?? `Document ${c.document_id.slice(0, 8)}`}
                </span>
                {typeof c.page_number === "number" && (
                  <span className="shrink-0 text-muted">Page {c.page_number}</span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Message bubble
──────────────────────────────────────────────────────────── */
export function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 h-5">
      <span className="typing-dot h-1.5 w-1.5 rounded-full bg-muted" />
      <span className="typing-dot h-1.5 w-1.5 rounded-full bg-muted" />
      <span className="typing-dot h-1.5 w-1.5 rounded-full bg-muted" />
    </div>
  );
}

export function MessageBubble({
  message,
  isStreamingThis,
  documentsById,
  onFeedback,
  feedbackGiven,
  onSpeak,
  speaking,
}: {
  message: ChatMessage;
  isStreamingThis: boolean;
  documentsById: Record<string, RagDocument>;
  onFeedback?: (rating: 1 | -1) => void;
  feedbackGiven?: 1 | -1 | null;
  onSpeak?: () => void;
  speaking?: boolean;
}) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end animate-fadeIn">
        <div className="max-w-[75%] rounded-2xl rounded-tr-sm bg-accent text-white px-4 py-2.5 text-sm whitespace-pre-wrap break-words">
          {message.attachmentKind === "image" && message.attachmentName && (
            <div className="flex items-center gap-1.5 text-xs opacity-80 mb-1">
              <ImageIcon size={12} />
              {message.attachmentName}
            </div>
          )}
          {message.attachmentKind === "voice" && (
            <div className="flex items-center gap-1.5 text-xs opacity-80 mb-1">
              <Mic size={12} />
              Voice message
            </div>
          )}
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start animate-fadeIn group">
      <div className="max-w-[85%] w-full">
        <div className="rounded-2xl rounded-tl-sm bg-card border border-border px-4 py-3 text-sm text-primary">
          {message.content ? (
            <div className="prose-chat">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          ) : isStreamingThis ? (
            <TypingIndicator />
          ) : null}
          {isStreamingThis && message.content && (
            <span className="inline-block w-1.5 h-4 bg-accent/70 align-middle ml-0.5 animate-pulse" />
          )}

          {message.citations && message.citations.length > 0 && (
            <CitationList citations={message.citations} documentsById={documentsById} />
          )}

          {message.needsHumanReview && (
            <div className="mt-2 text-[11px] text-[var(--warning)] flex items-center gap-1">
              Flagged for review — this answer may need a closer look.
            </div>
          )}
        </div>

        {!isStreamingThis && message.content && (onFeedback || onSpeak) && (
          <div className="flex items-center gap-1 mt-1 pl-1 opacity-0 group-hover:opacity-100 transition-opacity">
            {onSpeak && (
              <Tooltip label="Read aloud">
                <IconButton label="Read aloud" onClick={onSpeak} className="h-7 w-7">
                  {speaking ? <Loader2 size={13} className="animate-spin" /> : <Volume2 size={13} />}
                </IconButton>
              </Tooltip>
            )}
            {onFeedback && (
              <>
                <Tooltip label="Good response">
                  <IconButton
                    label="Good response"
                    active={feedbackGiven === 1}
                    onClick={() => onFeedback(1)}
                    className="h-7 w-7"
                  >
                    <ThumbsUp size={13} />
                  </IconButton>
                </Tooltip>
                <Tooltip label="Bad response">
                  <IconButton
                    label="Bad response"
                    active={feedbackGiven === -1}
                    onClick={() => onFeedback(-1)}
                    className="h-7 w-7"
                  >
                    <ThumbsDown size={13} />
                  </IconButton>
                </Tooltip>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Chat input — text, image attach, voice
──────────────────────────────────────────────────────────── */
export type VoiceState = "idle" | "recording" | "uploading" | "transcribing" | "generating" | "speaking";

export function ChatInput({
  onSendText,
  onSendImage,
  onSendVoice,
  disabled,
  voiceState,
}: {
  onSendText: (text: string) => void;
  onSendImage: (file: File, caption: string) => void;
  onSendVoice: (blob: Blob) => void;
  disabled: boolean;
  voiceState: VoiceState;
}) {
  const [text, setText] = useState("");
  const [pendingImage, setPendingImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const [recording, setRecording] = useState(false);

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }, [text]);

  const busy = disabled || voiceState !== "idle";

  const handlePickImage = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPendingImage(file);
    setImagePreview(URL.createObjectURL(file));
    e.target.value = "";
  };

  const clearImage = () => {
    setPendingImage(null);
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setImagePreview(null);
  };

  const handleSend = () => {
    if (busy) return;
    if (pendingImage) {
      onSendImage(pendingImage, text.trim() || "Describe this image.");
      clearImage();
      setText("");
      return;
    }
    if (!text.trim()) return;
    onSendText(text.trim());
    setText("");
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        onSendVoice(blob);
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setRecording(true);
    } catch {
      setRecording(false);
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  };

  // The backend runs transcription + the full agent graph inside one
  // POST /chat/message/voice call, so the frontend can't observe those
  // as separate steps — "uploading" covers both honestly.
  const voiceLabel: Record<VoiceState, string> = {
    idle: "Start voice input",
    recording: "Stop recording",
    uploading: "Transcribing & generating response…",
    transcribing: "Transcribing & generating response…",
    generating: "Transcribing & generating response…",
    speaking: "Speaking…",
  };

  return (
    <div className="border-t border-border bg-base px-3 py-3 md:px-6 md:py-4">
      <div className="max-w-3xl mx-auto">
        {voiceState !== "idle" && (
          <div className="mb-2 flex items-center gap-2 text-xs text-secondary">
            <Loader2 size={12} className="animate-spin" />
            {voiceLabel[voiceState]}
          </div>
        )}

        <div className="rounded-2xl border border-border bg-card focus-within:border-accent focus-within:ring-2 focus-within:ring-[var(--accent-glow)] transition-colors">
          {imagePreview && (
            <div className="flex items-center gap-2 px-3 pt-3">
              <div className="relative">
                <img src={imagePreview} alt="Attachment preview" className="h-14 w-14 rounded-lg object-cover border border-border" />
                <button
                  onClick={clearImage}
                  aria-label="Remove image"
                  className="absolute -top-1.5 -right-1.5 h-5 w-5 rounded-full bg-elevated border border-border flex items-center justify-center text-muted hover:text-primary"
                >
                  <X size={11} />
                </button>
              </div>
              <span className="text-xs text-muted">Image attached — describe what you want to know</span>
            </div>
          )}

          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={pendingImage ? "Ask something about this image..." : "Ask a question about your documents..."}
            disabled={busy}
            rows={1}
            className="w-full resize-none bg-transparent px-4 py-3 text-sm text-primary placeholder:text-muted outline-none disabled:opacity-60"
          />

          <div className="flex items-center justify-between px-2 pb-2">
            <div className="flex items-center gap-0.5">
              <Tooltip label="Attach image">
                <IconButton label="Attach image" onClick={() => fileInputRef.current?.click()} disabled={busy}>
                  <Paperclip size={16} />
                </IconButton>
              </Tooltip>
              <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handlePickImage} />

              <Tooltip label={voiceLabel[recording ? "recording" : "idle"]}>
                <IconButton
                  label={voiceLabel[recording ? "recording" : "idle"]}
                  active={recording}
                  onClick={recording ? stopRecording : startRecording}
                  disabled={busy && !recording}
                  className={recording ? "recording-pulse text-[var(--danger)]" : undefined}
                >
                  {recording ? <Square size={14} /> : <Mic size={16} />}
                </IconButton>
              </Tooltip>
            </div>

            <IconButton
              label="Send message"
              onClick={handleSend}
              disabled={busy || (!text.trim() && !pendingImage)}
              className="bg-accent text-white hover:bg-[var(--accent-hover)] disabled:opacity-40"
            >
              <Send size={15} />
            </IconButton>
          </div>
        </div>
        <p className="mt-1.5 text-[11px] text-muted text-center hidden md:block">
          Press Enter to send, Shift+Enter for a new line
        </p>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Documents panel
──────────────────────────────────────────────────────────── */
export function DocumentRow({
  doc,
  onDelete,
  deleting,
}: {
  doc: RagDocument;
  onDelete: () => void;
  deleting: boolean;
}) {
  return (
    <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-hover transition-colors group">
      <FileText size={16} className="text-muted shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-primary truncate">{doc.filename}</p>
        <p className="text-[11px] text-muted uppercase">{doc.file_type}</p>
      </div>
      <StatusBadge status={doc.status} />
      <IconButton
        label="Delete document"
        onClick={onDelete}
        disabled={deleting}
        className="opacity-0 group-hover:opacity-100 hover:text-[var(--danger)]"
      >
        {deleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
      </IconButton>
    </div>
  );
}

export function DocumentsPanel({
  documents,
  loading,
  uploading,
  onUpload,
  onDelete,
  deletingId,
}: {
  documents: RagDocument[];
  loading: boolean;
  uploading: boolean;
  onUpload: (file: File) => void;
  onDelete: (id: string) => void;
  deletingId: string | null;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFiles = (files: FileList | null) => {
    const file = files?.[0];
    if (file) onUpload(file);
  };

  return (
    <div className="space-y-4">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFiles(e.dataTransfer.files);
        }}
        onClick={() => fileInputRef.current?.click()}
        className={clsx(
          "border-2 border-dashed rounded-xl px-4 py-8 text-center cursor-pointer transition-colors",
          dragOver ? "border-accent bg-[var(--accent-muted)]" : "border-border hover:border-[var(--border-light)]"
        )}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.csv"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
        {uploading ? (
          <div className="flex flex-col items-center gap-2 text-secondary text-sm">
            <Loader2 size={20} className="animate-spin" />
            Uploading &amp; processing...
          </div>
        ) : (
          <div className="flex flex-col items-center gap-1.5">
            <Paperclip size={20} className="text-muted" />
            <p className="text-sm text-secondary">Drop a file here or click to upload</p>
            <p className="text-xs text-muted">PDF, DOCX, or CSV — up to 10 MB</p>
          </div>
        )}
      </div>

      <div>
        {loading ? (
          <div className="flex items-center justify-center py-8 text-sm text-secondary gap-2">
            <Loader2 size={14} className="animate-spin" /> Loading documents...
          </div>
        ) : documents.length === 0 ? (
          <EmptyState icon={<FileText size={22} />} title="No documents uploaded" description="Upload a document so the assistant can answer questions grounded in it." />
        ) : (
          <div className="space-y-0.5">
            {documents.map((d) => (
              <DocumentRow key={d.id} doc={d} onDelete={() => onDelete(d.id)} deleting={deletingId === d.id} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Settings modal — profile update (PATCH /users/me)
──────────────────────────────────────────────────────────── */
export function SettingsModal({
  open,
  onClose,
  user,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  user: AuthUser | null;
  onSaved: (patch: Partial<AuthUser>) => void;
}) {
  const toast = useToast();
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [username, setUsername] = useState(user?.username ?? "");
  const [phone, setPhone] = useState(user?.phone_number ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setFullName(user?.full_name ?? "");
      setUsername(user?.username ?? "");
      setPhone(user?.phone_number ?? "");
      setError("");
    }
  }, [open, user]);

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      const { data } = await usersAPI.updateMe({
        full_name: fullName,
        username,
        phone_number: phone,
      });
      onSaved({ full_name: data.full_name, username: data.username, phone_number: data.phone_number });
      toast.push("Profile updated", "success");
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Could not update profile");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Settings" size="sm">
      <div className="space-y-4">
        <Field label="Email">
          <Input value={user?.email ?? ""} disabled />
        </Field>
        <Field label="Username">
          <Input value={username} onChange={(e) => setUsername(e.target.value)} />
        </Field>
        <Field label="Full name">
          <Input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Optional" />
        </Field>
        <Field label="Phone number">
          <Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Optional" />
        </Field>
        {error && <p className="text-xs text-[var(--danger)]">{error}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" size="sm" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button size="sm" onClick={handleSave} loading={saving}>
            Save changes
          </Button>
        </div>
      </div>
    </Modal>
  );
}