import { useMemo, useState, type ReactNode } from "react";
import {
  Activity,
  BarChart3,
  ChevronLeft,
  ChevronRight,
  Coins,
  FileText,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Search,
  Shield,
  Users as UsersIcon,
} from "lucide-react";
import clsx from "clsx";
import type { AdminUser, AuditLog, UsageStats } from "../types";
import type { AuthUser } from "../store/authStore";
import { Avatar, Badge, Button, ConfirmDialog, EmptyState, StatusBadge } from "./ui";

export type AdminSection = "overview" | "users" | "audit-logs";

/* ────────────────────────────────────────────────────────────
   Admin sidebar
──────────────────────────────────────────────────────────── */
export function AdminSidebar({
  section,
  onSectionChange,
  user,
  onBackToChat,
  onLogout,
  open,
  onClose,
}: {
  section: AdminSection;
  onSectionChange: (s: AdminSection) => void;
  user: AuthUser | null;
  onBackToChat: () => void;
  onLogout: () => void;
  open: boolean;
  onClose: () => void;
}) {
  const items: { key: AdminSection; label: string; icon: ReactNode }[] = [
    { key: "overview", label: "Dashboard", icon: <LayoutDashboard size={16} /> },
    { key: "users", label: "Users", icon: <UsersIcon size={16} /> },
    { key: "audit-logs", label: "Audit Logs", icon: <Activity size={16} /> },
  ];

  const content = (
    <div className="flex flex-col h-full bg-elevated border-r border-border w-[240px]">
      <div className="flex items-center gap-2 px-4 h-14 shrink-0 border-b border-border">
        <Shield size={16} className="text-accent" />
        <span className="text-sm font-semibold text-primary">Admin</span>
      </div>

      <nav className="flex-1 p-2 space-y-0.5">
        {items.map((item) => (
          <button
            key={item.key}
            onClick={() => onSectionChange(item.key)}
            className={clsx(
              "w-full flex items-center gap-2.5 rounded-lg px-3 h-9 text-sm transition-colors",
              section === item.key
                ? "bg-[var(--accent-muted)] text-accent font-medium"
                : "text-secondary hover:text-primary hover:bg-hover"
            )}
          >
            {item.icon}
            {item.label}
          </button>
        ))}
      </nav>

      <div className="p-2 border-t border-border space-y-0.5">
        <button
          onClick={onBackToChat}
          className="w-full flex items-center gap-2.5 rounded-lg px-3 h-9 text-sm text-secondary hover:text-primary hover:bg-hover transition-colors"
        >
          <MessageSquare size={15} />
          Back to chat
        </button>
        <div className="flex items-center gap-2.5 px-3 h-11">
          <Avatar name={user?.username || user?.email || "?"} size={26} />
          <span className="text-xs text-secondary truncate">{user?.email}</span>
        </div>
        <button
          onClick={onLogout}
          className="w-full flex items-center gap-2.5 rounded-lg px-3 h-9 text-sm text-secondary hover:text-[var(--danger)] hover:bg-hover transition-colors"
        >
          <LogOut size={15} />
          Log out
        </button>
      </div>
    </div>
  );

  return (
    <>
      <div className="hidden md:block shrink-0">{content}</div>
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
   Overview — stat cards
──────────────────────────────────────────────────────────── */
const statConfig: { key: keyof UsageStats; label: string; icon: ReactNode; format?: (v: number) => string }[] = [
  { key: "total_chats", label: "Total Chats", icon: <MessageSquare size={16} /> },
  { key: "total_messages", label: "Total Messages", icon: <BarChart3 size={16} /> },
  { key: "total_documents", label: "Documents", icon: <FileText size={16} /> },
  { key: "total_tokens_used", label: "Token Usage", icon: <Activity size={16} /> },
  {
    key: "total_cost_usd",
    label: "Estimated Cost",
    icon: <Coins size={16} />,
    format: (v) => `$${v.toFixed(4)}`,
  },
];

export function UsageStatsGrid({ usage }: { usage: UsageStats }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
      {statConfig.map((cfg) => {
        const raw = usage[cfg.key];
        const value = cfg.format ? cfg.format(Number(raw)) : Number(raw).toLocaleString();
        return (
          <div key={cfg.key} className="rounded-xl border border-border bg-card p-4">
            <div className="flex items-center gap-2 text-muted mb-2">
              {cfg.icon}
              <span className="text-xs">{cfg.label}</span>
            </div>
            <p className="text-2xl font-semibold text-primary">{value}</p>
          </div>
        );
      })}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Pagination
──────────────────────────────────────────────────────────── */
export function Pagination({
  offset,
  limit,
  total,
  onChange,
}: {
  offset: number;
  limit: number;
  total: number;
  onChange: (offset: number) => void;
}) {
  if (total <= limit) return null;
  const page = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(total / limit);

  return (
    <div className="flex items-center justify-between px-1 pt-3 text-xs text-secondary">
      <span>
        Showing {offset + 1}–{Math.min(offset + limit, total)} of {total}
      </span>
      <div className="flex items-center gap-2">
        <button
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - limit))}
          className="h-7 w-7 flex items-center justify-center rounded-md border border-border disabled:opacity-40 hover:bg-hover"
        >
          <ChevronLeft size={14} />
        </button>
        <span>
          Page {page} of {totalPages}
        </span>
        <button
          disabled={offset + limit >= total}
          onClick={() => onChange(offset + limit)}
          className="h-7 w-7 flex items-center justify-center rounded-md border border-border disabled:opacity-40 hover:bg-hover"
        >
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Users table
──────────────────────────────────────────────────────────── */
export function UsersTable({
  users,
  loading,
  onDeactivate,
  deactivatingId,
}: {
  users: AdminUser[];
  loading: boolean;
  onDeactivate: (userId: string) => void;
  deactivatingId: string | null;
}) {
  const [search, setSearch] = useState("");
  const [confirmTarget, setConfirmTarget] = useState<AdminUser | null>(null);

  const filtered = useMemo(
    () =>
      search.trim()
        ? users.filter(
            (u) =>
              u.email.toLowerCase().includes(search.toLowerCase()) ||
              u.username.toLowerCase().includes(search.toLowerCase())
          )
        : users,
    [users, search]
  );

  return (
    <div className="space-y-3">
      <div className="relative max-w-xs">
        <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search users..."
          className="w-full h-9 rounded-lg bg-elevated border border-border pl-8 pr-3 text-sm text-primary placeholder:text-muted outline-none focus:border-accent"
        />
      </div>

      <div className="rounded-xl border border-border overflow-hidden">
        {loading ? (
          <div className="py-10 text-center text-sm text-secondary">Loading users...</div>
        ) : filtered.length === 0 ? (
          <EmptyState icon={<UsersIcon size={20} />} title="No users found" />
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-elevated text-left">
              <tr>
                <th className="px-4 py-2.5 font-medium text-secondary text-xs">User</th>
                <th className="px-4 py-2.5 font-medium text-secondary text-xs">Email</th>
                <th className="px-4 py-2.5 font-medium text-secondary text-xs">Role</th>
                <th className="px-4 py-2.5 font-medium text-secondary text-xs">Status</th>
                <th className="px-4 py-2.5 font-medium text-secondary text-xs">Created</th>
                <th className="px-4 py-2.5 font-medium text-secondary text-xs text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filtered.map((u) => (
                <tr key={u.id} className="hover:bg-hover/50 transition-colors">
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2.5">
                      <Avatar name={u.username} size={26} />
                      <span className="text-primary">{u.username}</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-secondary">{u.email}</td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={u.role} />
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={u.is_active ? "active" : "inactive"} />
                  </td>
                  <td className="px-4 py-2.5 text-secondary">{new Date(u.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-2.5 text-right">
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={!u.is_active || deactivatingId === u.id}
                      loading={deactivatingId === u.id}
                      onClick={() => setConfirmTarget(u)}
                    >
                      {u.is_active ? "Deactivate" : "Deactivated"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <ConfirmDialog
        open={!!confirmTarget}
        title="Deactivate user"
        description={confirmTarget ? `${confirmTarget.username} (${confirmTarget.email}) will lose access immediately. This cannot be undone from here.` : ""}
        confirmLabel="Deactivate"
        danger
        onCancel={() => setConfirmTarget(null)}
        onConfirm={() => {
          if (confirmTarget) onDeactivate(confirmTarget.id);
          setConfirmTarget(null);
        }}
      />
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Audit log table
──────────────────────────────────────────────────────────── */
function formatDetail(detail: Record<string, unknown>): string {
  const entries = Object.entries(detail ?? {});
  if (entries.length === 0) return "—";
  return entries.map(([k, v]) => `${k.replace(/_/g, " ")}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`).join(" · ");
}

export function AuditLogTable({ logs, loading }: { logs: AuditLog[]; loading: boolean }) {
  if (loading) return <div className="py-10 text-center text-sm text-secondary">Loading audit logs...</div>;
  if (logs.length === 0) return <EmptyState icon={<Activity size={20} />} title="No audit logs found" />;

  return (
    <div className="rounded-xl border border-border divide-y divide-border overflow-hidden">
      {logs.map((log) => (
        <div key={log.id} className="flex items-start gap-3 px-4 py-3">
          <div className="h-7 w-7 rounded-full bg-[var(--accent-muted)] flex items-center justify-center shrink-0 mt-0.5">
            <Activity size={13} className="text-accent" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge tone="accent">{log.action}</Badge>
              <span className="text-xs text-muted">{new Date(log.created_at).toLocaleString()}</span>
            </div>
            <p className="text-xs text-secondary mt-1 truncate">{formatDetail(log.detail)}</p>
          </div>
        </div>
      ))}
    </div>
  );
}