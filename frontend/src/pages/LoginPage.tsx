import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { api, usersAPI } from "../api/client";
import { useAuthStore } from "../store/authStore";
import { Button, Field, InlineAlert, Input, PasswordInput } from "../components/ui";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { setTokens, setUser } = useAuthStore();

  const handleLogin = async () => {
    if (!email.trim() || !password.trim() || loading) return;
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/login", { email, password });
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
      setError(err.response?.data?.detail || "Invalid email or password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-base px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center gap-2 mb-8">
          <div className="h-11 w-11 rounded-xl bg-accent flex items-center justify-center text-white">
            <Sparkles size={20} />
          </div>
          <h1 className="text-lg font-semibold text-primary">Welcome back</h1>
          <p className="text-sm text-secondary">Log in to your Agentic RAG workspace</p>
        </div>

        <div className="bg-card border border-border rounded-2xl p-6 space-y-4">
          {error && <InlineAlert tone="danger">{error}</InlineAlert>}

          <Field label="Email">
            <Input
              type="email"
              autoComplete="email"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            />
          </Field>

          <Field label="Password">
            <PasswordInput
              autoComplete="current-password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            />
          </Field>

          <Button
            className="w-full"
            onClick={handleLogin}
            disabled={!email.trim() || !password.trim()}
            loading={loading}
          >
            Log in
          </Button>
        </div>

        <p className="text-center text-sm text-secondary mt-5">
          No account?{" "}
          <Link to="/signup" className="text-accent hover:underline font-medium">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}