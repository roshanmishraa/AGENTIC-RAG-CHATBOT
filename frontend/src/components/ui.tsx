import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type TextareaHTMLAttributes,
} from "react";
import { createPortal } from "react-dom";
import { AlertTriangle, CheckCircle2, Eye, EyeOff, Info, Loader2, X, XCircle } from "lucide-react";
import clsx from "clsx";

/* ────────────────────────────────────────────────────────────
   Button
──────────────────────────────────────────────────────────── */
type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: ReactNode;
}

const buttonVariants: Record<ButtonVariant, string> = {
  primary: "bg-accent text-white hover:bg-[var(--accent-hover)] disabled:opacity-50",
  secondary: "bg-card text-primary border border-border hover:bg-hover disabled:opacity-50",
  ghost: "text-secondary hover:text-primary hover:bg-hover disabled:opacity-40",
  danger: "bg-[var(--danger)] text-white hover:brightness-110 disabled:opacity-50",
};

const buttonSizes: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-xs gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
  lg: "h-11 px-5 text-sm gap-2",
};

export function Button({
  variant = "primary",
  size = "md",
  loading,
  icon,
  disabled,
  className,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={clsx(
        "inline-flex items-center justify-center rounded-lg font-medium transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2",
        buttonVariants[variant],
        buttonSizes[size],
        className
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <Loader2 size={15} className="animate-spin" /> : icon}
      {children}
    </button>
  );
}

export function IconButton({
  label,
  active,
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string; active?: boolean }) {
  return (
    <button
      aria-label={label}
      title={label}
      className={clsx(
        "inline-flex items-center justify-center h-9 w-9 rounded-lg transition-colors",
        "text-secondary hover:text-primary hover:bg-hover disabled:opacity-40 disabled:pointer-events-none",
        "focus-visible:outline-2 focus-visible:outline-offset-2",
        active && "bg-[var(--accent-muted)] text-accent",
        className
      )}
      {...rest}
    >
      {children}
    </button>
  );
}

/* ────────────────────────────────────────────────────────────
   Inputs
──────────────────────────────────────────────────────────── */
interface FieldWrapperProps {
  label?: string;
  error?: string;
  hint?: string;
  htmlFor?: string;
  children: ReactNode;
}

export function Field({ label, error, hint, htmlFor, children }: FieldWrapperProps) {
  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={htmlFor} className="block text-xs font-medium text-secondary">
          {label}
        </label>
      )}
      {children}
      {error ? (
        <p className="text-xs text-[var(--danger)]">{error}</p>
      ) : hint ? (
        <p className="text-xs text-muted">{hint}</p>
      ) : null}
    </div>
  );
}

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={clsx(
        "w-full h-11 rounded-lg bg-elevated border border-border px-3.5 text-sm text-primary",
        "placeholder:text-muted outline-none transition-colors",
        "focus:border-accent focus:ring-2 focus:ring-[var(--accent-glow)]",
        "disabled:opacity-50",
        className
      )}
      {...rest}
    />
  );
}

export function PasswordInput({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input
        type={visible ? "text" : "password"}
        className={clsx(
          "w-full h-11 rounded-lg bg-elevated border border-border pl-3.5 pr-10 text-sm text-primary",
          "placeholder:text-muted outline-none transition-colors",
          "focus:border-accent focus:ring-2 focus:ring-[var(--accent-glow)]",
          "disabled:opacity-50",
          className
        )}
        {...rest}
      />
      <button
        type="button"
        tabIndex={-1}
        aria-label={visible ? "Hide password" : "Show password"}
        onClick={() => setVisible((v) => !v)}
        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-secondary"
      >
        {visible ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  );
}

export function TextArea({ className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={clsx(
        "w-full rounded-lg bg-elevated border border-border px-3.5 py-2.5 text-sm text-primary",
        "placeholder:text-muted outline-none transition-colors resize-none",
        "focus:border-accent focus:ring-2 focus:ring-[var(--accent-glow)]",
        "disabled:opacity-50",
        className
      )}
      {...rest}
    />
  );
}

/* ────────────────────────────────────────────────────────────
   Badge / StatusBadge
──────────────────────────────────────────────────────────── */
type BadgeTone = "neutral" | "success" | "warning" | "danger" | "info" | "accent";

const badgeTones: Record<BadgeTone, string> = {
  neutral: "bg-hover text-secondary",
  success: "bg-[rgba(34,197,94,0.14)] text-[var(--success)]",
  warning: "bg-[rgba(245,158,11,0.14)] text-[var(--warning)]",
  danger: "bg-[rgba(239,68,68,0.14)] text-[var(--danger)]",
  info: "bg-[rgba(56,189,248,0.14)] text-[var(--info)]",
  accent: "bg-[var(--accent-muted)] text-accent",
};

export function Badge({ tone = "neutral", children }: { tone?: BadgeTone; children: ReactNode }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium uppercase tracking-wide",
        badgeTones[tone]
      )}
    >
      {children}
    </span>
  );
}

const statusToneMap: Record<string, BadgeTone> = {
  ready: "success",
  active: "success",
  processing: "warning",
  uploading: "warning",
  failed: "danger",
  inactive: "danger",
  admin: "accent",
  user: "neutral",
};

export function StatusBadge({ status }: { status: string }) {
  const tone = statusToneMap[status.toLowerCase()] ?? "neutral";
  return <Badge tone={tone}>{status}</Badge>;
}

/* ────────────────────────────────────────────────────────────
   Spinner / Loading / Empty / Error states
──────────────────────────────────────────────────────────── */
export function Spinner({ size = 16, className }: { size?: number; className?: string }) {
  return <Loader2 size={size} className={clsx("animate-spin text-secondary", className)} />;
}

export function LoadingState({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-sm text-secondary">
      <Spinner size={15} />
      {label}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center gap-2 py-12 px-6">
      {icon && <div className="text-muted mb-1">{icon}</div>}
      <p className="text-sm font-medium text-primary">{title}</p>
      {description && <p className="text-xs text-secondary max-w-xs">{description}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center text-center gap-3 py-10 px-6">
      <XCircle size={22} className="text-[var(--danger)]" />
      <p className="text-sm text-secondary">{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function InlineAlert({
  tone = "danger",
  children,
  onDismiss,
}: {
  tone?: "danger" | "warning" | "info";
  children: ReactNode;
  onDismiss?: () => void;
}) {
  const icons = { danger: XCircle, warning: AlertTriangle, info: Info };
  const Icon = icons[tone];
  const toneClass = {
    danger: "bg-[rgba(239,68,68,0.08)] border-[rgba(239,68,68,0.35)] text-[var(--danger)]",
    warning: "bg-[rgba(245,158,11,0.08)] border-[rgba(245,158,11,0.35)] text-[var(--warning)]",
    info: "bg-[rgba(56,189,248,0.08)] border-[rgba(56,189,248,0.35)] text-[var(--info)]",
  }[tone];
  return (
    <div className={clsx("flex items-start gap-2.5 rounded-lg border px-3.5 py-2.5 text-sm", toneClass)}>
      <Icon size={16} className="mt-0.5 shrink-0" />
      <div className="flex-1 min-w-0">{children}</div>
      {onDismiss && (
        <button onClick={onDismiss} className="shrink-0 opacity-70 hover:opacity-100">
          <X size={14} />
        </button>
      )}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Modal
──────────────────────────────────────────────────────────── */
export function Modal({
  open,
  onClose,
  title,
  children,
  size = "md",
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  size?: "sm" | "md" | "lg";
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const widths = { sm: "max-w-sm", md: "max-w-md", lg: "max-w-2xl" };

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={clsx(
          "relative w-full bg-card border border-border rounded-xl shadow-2xl animate-fadeIn",
          widths[size]
        )}
      >
        {title && (
          <div className="flex items-center justify-between px-5 py-4 border-b border-border">
            <h2 className="text-sm font-semibold text-primary">{title}</h2>
            <IconButton label="Close" onClick={onClose}>
              <X size={16} />
            </IconButton>
          </div>
        )}
        <div className="p-5">{children}</div>
      </div>
    </div>,
    document.body
  );
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  danger,
  loading,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  danger?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal open={open} onClose={onCancel} title={title} size="sm">
      {description && <p className="text-sm text-secondary mb-5">{description}</p>}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" size="sm" onClick={onCancel} disabled={loading}>
          Cancel
        </Button>
        <Button variant={danger ? "danger" : "primary"} size="sm" onClick={onConfirm} loading={loading}>
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}

/* ────────────────────────────────────────────────────────────
   Toast system
──────────────────────────────────────────────────────────── */
type ToastTone = "success" | "danger" | "info";

interface ToastItem {
  id: number;
  tone: ToastTone;
  message: string;
}

interface ToastContextValue {
  push: (message: string, tone?: ToastTone) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}

const toastIcons: Record<ToastTone, ReactNode> = {
  success: <CheckCircle2 size={16} className="text-[var(--success)]" />,
  danger: <XCircle size={16} className="text-[var(--danger)]" />,
  info: <Info size={16} className="text-[var(--info)]" />,
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const counter = useRef(0);

  const push = useCallback((message: string, tone: ToastTone = "info") => {
    const id = ++counter.current;
    setToasts((prev) => [...prev, { id, message, tone }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      {createPortal(
        <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 w-80 max-w-[calc(100vw-2rem)]">
          {toasts.map((t) => (
            <div
              key={t.id}
              className="flex items-start gap-2.5 bg-card border border-border rounded-lg shadow-xl px-3.5 py-3 text-sm text-primary animate-fadeIn"
            >
              {toastIcons[t.tone]}
              <span className="flex-1 min-w-0">{t.message}</span>
            </div>
          ))}
        </div>,
        document.body
      )}
    </ToastContext.Provider>
  );
}

/* ────────────────────────────────────────────────────────────
   Tooltip (simple, for icon-only buttons)
──────────────────────────────────────────────────────────── */
export function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span className="relative group inline-flex">
      {children}
      <span
        role="tooltip"
        className={clsx(
          "pointer-events-none absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap",
          "rounded-md bg-elevated border border-border px-2 py-1 text-[11px] text-secondary",
          "opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity z-20"
        )}
      >
        {label}
      </span>
    </span>
  );
}

/* ────────────────────────────────────────────────────────────
   Avatar
──────────────────────────────────────────────────────────── */
export function Avatar({ name, size = 32 }: { name: string; size?: number }) {
  const initial = (name || "?").trim().charAt(0).toUpperCase();
  return (
    <div
      className="flex items-center justify-center rounded-full bg-[var(--accent-muted)] text-accent font-semibold shrink-0"
      style={{ width: size, height: size, fontSize: size * 0.42 }}
    >
      {initial}
    </div>
  );
}