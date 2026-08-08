import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuthStore } from "../store/authStore";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { setTokens, setUser } = useAuthStore();

  const handleLogin = async () => {
    setError("");
    try {
      const { data } = await api.post("/auth/login", { email, password });
      setTokens(data.access_token, data.refresh_token);
      const { data: me } = await api.get("/users/me");
      setUser({ id: me.id, email: me.email, role: me.role });
      navigate("/chat");
    } catch {
      setError("Invalid email or password");
    }
  };

  return (
    <div className="flex items-center justify-center h-screen bg-gray-50">
      <div className="bg-white p-8 rounded-xl shadow-md w-96 space-y-4">
        <h1 className="text-xl font-semibold text-center">Log in</h1>

        {error && <p className="text-red-500 text-sm">{error}</p>}

        <input
          className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
          placeholder="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleLogin()}
        />

        <input
          type="password"
          className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleLogin()}
        />

        <button
          onClick={handleLogin}
          disabled={!email.trim() || !password.trim()}
          className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          Log in
        </button>

        <p className="text-center text-sm">
          No account?{" "}
          <Link to="/signup" className="text-blue-600 hover:underline">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}