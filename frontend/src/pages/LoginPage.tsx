import { FormEvent, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../api";
import { useAuth } from "../auth";
import { Alert, Button, LoadingBlock, TextField } from "../components/ui";

export function LoginPage() {
  const { user, loading, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (loading) return <LoadingBlock />;
  if (user) return <Navigate to="/" replace />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
      const from = (location.state as { from?: string } | null)?.from || "/";
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось войти");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-8rem)] w-full max-w-md flex-col justify-center px-4 py-10">
      <h1 className="text-2xl font-semibold">Вход</h1>
      <p className="mt-1 text-sm text-zinc-400">Продолжите решать задачи и участвовать в турнирах.</p>
      <form onSubmit={onSubmit} className="card mt-6 space-y-4 p-6">
        {error && <Alert>{error}</Alert>}
        <TextField label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
        <TextField label="Пароль" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
        <Button type="submit" loading={busy} className="w-full">
          Войти
        </Button>
        <p className="text-center text-sm text-zinc-400">
          Нет аккаунта?{" "}
          <Link to="/register" className="text-violet-300 hover:text-violet-200">
            Зарегистрироваться
          </Link>
          {" · "}
          <Link to="/register-organization" className="text-violet-300 hover:text-violet-200">
            Организация
          </Link>
        </p>
      </form>
    </div>
  );
}
