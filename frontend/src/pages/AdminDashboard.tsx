import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function AdminDashboard() {
  const [usage, setUsage] = useState<any>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);

  useEffect(() => {
    api.get("/admin/usage").then((r) => setUsage(r.data));
    api.get("/admin/users").then((r) => setUsers(r.data));
    api.get("/admin/audit-logs").then((r) => setLogs(r.data));
  }, []);

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      <h1 className="text-2xl font-semibold">Admin Dashboard</h1>

      {usage && (
        <div className="grid grid-cols-5 gap-4">
          {Object.entries(usage).map(([key, value]) => (
            <div key={key} className="bg-white p-4 rounded-lg shadow-sm">
              <p className="text-xs text-gray-500">{key.replace(/_/g, " ")}</p>
              <p className="text-xl font-semibold">{String(value)}</p>
            </div>
          ))}
        </div>
      )}

      <div>
        <h2 className="font-medium mb-2">Users</h2>
        <table className="w-full text-sm bg-white rounded-lg overflow-hidden">
          <thead className="bg-gray-100">
            <tr><th className="p-2 text-left">Email</th><th className="p-2 text-left">Role</th><th className="p-2 text-left">Active</th></tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-t">
                <td className="p-2">{u.email}</td><td className="p-2">{u.role}</td><td className="p-2">{u.is_active ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div>
        <h2 className="font-medium mb-2">Recent Activity</h2>
        <div className="bg-white rounded-lg p-4 space-y-1 text-sm max-h-64 overflow-y-auto">
          {logs.map((l) => (
            <p key={l.id} className="text-gray-600">{l.action} — {new Date(l.created_at).toLocaleString()}</p>
          ))}
        </div>
      </div>
    </div>
  );
}