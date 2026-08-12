import { useMemo, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Check, Sparkles, X as XIcon } from "lucide-react";
import clsx from "clsx";
import { api, usersAPI } from "../api/client";
import { useAuthStore } from "../store/authStore";
import { Button, Field, InlineAlert, Input, PasswordInput } from "../components/ui";

// Mirrors app/api/v1/auth.py SignupRequest validators exactly —
// intentionally no stricter (or looser) rules than the backend.
function passwordChecks(password: string) {
  return [
    { label: "At least 8 characters", ok: password.length >= 8 },
    { label: "One uppercase letter", ok: /[A-Z]/.test(password) },
    { label: "One digit", ok: /[0-9]/.test(password) },
  ];
}

export default function SignupPage() {
  const [form, setForm] = useState({ email: "", username: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { setTokens, setUser } = useAuthStore();

  const checks = useMemo(() => passwordChecks(form.password), [form.password]);
  const usernameValid = form.username.trim().length >= 3;
  const passwordValid = checks.every((c) => c.ok);
  const canSubmit = !!form.email.trim() && usernameValid && passwordValid && !loading;

  const handleSignup = async () => {
    if (!canSubmit) return;
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/signup", form);
      setTokens(data.access_token, data.refresh_token);
      const { data: me } = await usersAPI.me();
      setUser({
        id: me.id,
        email: me.email,
        role: me.role,
        username: me.username,
        full_name: me.full_name,
        phone_number: me.phone_number,
      });
      navigate("/chat");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Signup failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-base px-4 py-8">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center gap-2 mb-8">
          <div className="h-11 w-11 rounded-xl bg-accent flex items-center justify-center text-white">
            <Sparkles size={20} />
          </div>
          <h1 className="text-lg font-semibold text-primary">Create your account</h1>
          <p className="text-sm text-secondary">Get started with Agentic RAG</p>
        </div>

        <div className="bg-card border border-border rounded-2xl p-6 space-y-4">
          {error && <InlineAlert tone="danger">{error}</InlineAlert>}

          <Field label="Email">
            <Input
              type="email"
              autoComplete="email"
              placeholder="you@company.com"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </Field>

          <Field label="Username" error={form.username && !usernameValid ? "Must be at least 3 characters" : undefined}>
            <Input
              autoComplete="username"
              placeholder="janedoe"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
            />
          </Field>

          <Field label="Password">
            <PasswordInput
              autoComplete="new-password"
              placeholder="••••••••"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              onKeyDown={(e) => e.key === "Enter" && handleSignup()}
            />
            <ul className="space-y-1 pt-1">
              {checks.map((c) => (
                <li
                  key={c.label}
                  className={clsx("flex items-center gap-1.5 text-xs", c.ok ? "text-[var(--success)]" : "text-muted")}
                >
                  {c.ok ? <Check size={12} /> : <XIcon size={12} />}
                  {c.label}
                </li>
              ))}
            </ul>
          </Field>

          <Button className="w-full" onClick={handleSignup} disabled={!canSubmit} loading={loading}>
            Create account
          </Button>
        </div>

        <p className="text-center text-sm text-secondary mt-5">
          Already have an account?{" "}
          <Link to="/login" className="text-accent hover:underline font-medium">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}