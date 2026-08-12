import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Menu } from "lucide-react";
import { useAuthStore } from "../store/authStore";
import { adminAPI, authAPI } from "../api/client";
import type { AdminUser, AuditLog, UsageStats } from "../types";
import {
  AdminSidebar,
  AuditLogTable,
  Pagination,
  UsageStatsGrid,
  UsersTable,
} from "../components/admin";
import type { AdminSection } from "../components/admin";
import { ErrorState, IconButton, LoadingState, useToast } from "../components/ui";

const PAGE_SIZE = 20;

const sectionTitles: Record<AdminSection, string> = {
  overview: "Dashboard",
  users: "Users",
  "audit-logs": "Audit Logs",
};

export default function AdminDashboard() {
  const navigate = useNavigate();
  const toast = useToast();
  const { user, logout } = useAuthStore();

  const [section, setSection] = useState<AdminSection>("overview");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [usageError, setUsageError] = useState(false);

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [usersTotal, setUsersTotal] = useState(0);
  const [usersOffset, setUsersOffset] = useState(0);
  const [usersLoading, setUsersLoading] = useState(false);
  const [deactivatingId, setDeactivatingId] = useState<string | null>(null);

  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [logsTotal, setLogsTotal] = useState(0);
  const [logsOffset, setLogsOffset] = useState(0);
  const [logsLoading, setLogsLoading] = useState(false);

  const loadUsage = useCallback(async () => {
    setUsageError(false);
    try {
      const { data } = await adminAPI.usage();
      setUsage(data);
    } catch {
      setUsageError(true);
    }
  }, []);

  const loadUsers = useCallback(async (offset: number) => {
    setUsersLoading(true);
    try {
      const { data } = await adminAPI.users(PAGE_SIZE, offset);
      setUsers(data.users);
      setUsersTotal(data.total);
    } catch {
      toast.push("Unable to load users", "danger");
    } finally {
      setUsersLoading(false);
    }
  }, [toast]);

  const loadLogs = useCallback(async (offset: number) => {
    setLogsLoading(true);
    try {
      const { data } = await adminAPI.auditLogs(PAGE_SIZE, offset);
      setLogs(data.logs);
      setLogsTotal(data.total);
    } catch {
      toast.push("Unable to load audit logs", "danger");
    } finally {
      setLogsLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    loadUsage();
  }, [loadUsage]);

  useEffect(() => {
    if (section === "users") loadUsers(usersOffset);
  }, [section, usersOffset, loadUsers]);

  useEffect(() => {
    if (section === "audit-logs") loadLogs(logsOffset);
  }, [section, logsOffset, loadLogs]);

  const handleDeactivate = async (userId: string) => {
    setDeactivatingId(userId);
    try {
      await adminAPI.deactivateUser(userId);
      toast.push("User deactivated", "success");
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, is_active: false } : u)));
    } catch (err: any) {
      toast.push(err.response?.data?.detail || "Could not deactivate user", "danger");
    } finally {
      setDeactivatingId(null);
    }
  };

  const handleLogout = async () => {
    try {
      const rt = useAuthStore.getState().refreshToken;
      if (rt) await authAPI.logout(rt);
    } catch {
      // best-effort
    }
    logout();
    navigate("/login");
  };

  return (
    <div className="flex h-screen bg-base overflow-hidden">
      <AdminSidebar
        section={section}
        onSectionChange={(s) => {
          setSection(s);
          setSidebarOpen(false);
        }}
        user={user}
        onBackToChat={() => navigate("/chat")}
        onLogout={handleLogout}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex items-center gap-2 h-14 px-4 border-b border-border shrink-0">
          <IconButton label="Open menu" onClick={() => setSidebarOpen(true)} className="md:hidden">
            <Menu size={18} />
          </IconButton>
          <h1 className="text-sm font-semibold text-primary">{sectionTitles[section]}</h1>
        </div>

        <div className="flex-1 overflow-y-auto p-4 md:p-6">
          <div className="max-w-5xl mx-auto">
            {section === "overview" &&
              (usageError ? (
                <ErrorState message="Unable to load usage statistics." onRetry={loadUsage} />
              ) : usage ? (
                <UsageStatsGrid usage={usage} />
              ) : (
                <LoadingState label="Loading usage statistics..." />
              ))}

            {section === "users" && (
              <>
                <UsersTable
                  users={users}
                  loading={usersLoading}
                  onDeactivate={handleDeactivate}
                  deactivatingId={deactivatingId}
                />
                <Pagination offset={usersOffset} limit={PAGE_SIZE} total={usersTotal} onChange={setUsersOffset} />
              </>
            )}

            {section === "audit-logs" && (
              <>
                <AuditLogTable logs={logs} loading={logsLoading} />
                <Pagination offset={logsOffset} limit={PAGE_SIZE} total={logsTotal} onChange={setLogsOffset} />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}