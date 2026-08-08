import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuthStore } from "../store/authStore";

export default function SignupPage() {
  const [form, setForm] = useState({ email: "", username: "", password: "" });
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { setTokens, setUser } = useAuthStore();

  const handleSignup = async () => {
    setError("");
    try {
      const { data } = await api.post("/auth/signup", form);
      setTokens(data.access_token, data.refresh_token);
      const { data: me } = await api.get("/users/me");
      setUser({ id: me.id, email: me.email, role: me.role });
      navigate("/chat");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Signup failed");
    }
  };

  return (
    <div className="flex items-center justify-center h-screen bg-gray-50">
      <div className="bg-white p-8 rounded-xl shadow-md w-96 space-y-3">
        <h1 className="text-xl font-semibold text-center">Sign up</h1>
        {error && <p className="text-red-500 text-sm">{error}</p>}

        <input
          className="w-full border rounded-lg px-3 py-2"
          placeholder="Email"
          onChange={(e) => setForm({ ...form, email: e.target.value })}
        />
        <input
          className="w-full border rounded-lg px-3 py-2"
          placeholder="Username"
          onChange={(e) => setForm({ ...form, username: e.target.value })}
        />
        <input
          type="password"
          className="w-full border rounded-lg px-3 py-2"
          placeholder="Password"
          onChange={(e) => setForm({ ...form, password: e.target.value })}
        />

        <button
          onClick={handleSignup}
          className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 transition-colors"
        >
          Create account
        </button>

        <p className="text-center text-sm">
          Already have an account?{" "}
          <Link to="/login" className="text-blue-600 hover:underline">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}