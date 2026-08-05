import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuthStore } from "../store/authStore";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otpMode, setOtpMode] = useState(false);
  const [otpSent, setOtpSent] = useState(false);
  const [otp, setOtp] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { setTokens, setUser } = useAuthStore();

  const afterLogin = async (accessToken: string, refreshToken: string) => {
    setTokens(accessToken, refreshToken);
    const { data: me } = await api.get("/users/me");
    setUser({ id: me.id, email: me.email, role: me.role });
    navigate("/chat");
  };

  const handlePasswordLogin = async () => {
    setError("");
    try {
      const { data } = await api.post("/auth/login", { email, password });
      await afterLogin(data.access_token, data.refresh_token);
    } catch {
      setError("Invalid email or password");
    }
  };

  const handleRequestOtp = async () => {
    setError("");
    try {
      await api.post("/auth/otp/request", { email });
      setOtpSent(true);
    } catch {
      setError("Failed to send OTP");
    }
  };

  const handleVerifyOtp = async () => {
    setError("");
    try {
      const { data } = await api.post("/auth/otp/verify", { email, otp });
      await afterLogin(data.access_token, data.refresh_token);
    } catch {
      setError("Invalid or expired OTP");
    }
  };

  const handleGoogleLogin = () => {
    window.location.href = `${import.meta.env.VITE_API_URL}/auth/google/login`;
  };

  return (
    <div className="flex items-center justify-center h-screen bg-gray-50">
      <div className="bg-white p-8 rounded-xl shadow-md w-96 space-y-4">
        <h1 className="text-xl font-semibold text-center">Log in</h1>
        {error && <p className="text-red-500 text-sm">{error}</p>}

        <input className="w-full border rounded-lg px-3 py-2" placeholder="Email"
          value={email} onChange={(e) => setEmail(e.target.value)} />

        {!otpMode ? (
          <>
            <input type="password" className="w-full border rounded-lg px-3 py-2" placeholder="Password"
              value={password} onChange={(e) => setPassword(e.target.value)} />
            <button onClick={handlePasswordLogin} className="w-full bg-blue-600 text-white py-2 rounded-lg">
              Log in
            </button>
            <button onClick={() => setOtpMode(true)} className="w-full text-sm text-blue-600">
              Log in with Email OTP instead
            </button>
          </>
        ) : !otpSent ? (
          <button onClick={handleRequestOtp} className="w-full bg-blue-600 text-white py-2 rounded-lg">
            Send OTP to email
          </button>
        ) : (
          <>
            <input className="w-full border rounded-lg px-3 py-2" placeholder="Enter 6-digit OTP"
              value={otp} onChange={(e) => setOtp(e.target.value)} />
            <button onClick={handleVerifyOtp} className="w-full bg-blue-600 text-white py-2 rounded-lg">
              Verify & Log in
            </button>
          </>
        )}

        <div className="text-center text-gray-400 text-sm">or</div>
        <button onClick={handleGoogleLogin} className="w-full border py-2 rounded-lg">
          Continue with Google
        </button>

        <p className="text-center text-sm">
          No account? <Link to="/signup" className="text-blue-600">Sign up</Link>
        </p>
      </div>
    </div>
  );
}