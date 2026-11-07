import { FormEvent, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ApiError } from "../api";
import { useAuth } from "../auth";
import { Alert, Button, LoadingBlock, TextField } from "../components/ui";

export function RegisterPage() {
  const { user, loading, register } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
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
      await register({ username, email, password });
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось зарегистрироваться");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-8rem)] w-full max-w-md flex-col justify-center px-4 py-10">
      <h1 className="text-2xl font-semibold">Регистрация участника</h1>
      <p className="mt-1 text-sm text-zinc-400">Имя — латиница, цифры и подчёркивание. Пароль от 6 символов.</p>
      <form onSubmit={onSubmit} className="card mt-6 space-y-4 p-6">
        {error && <Alert>{error}</Alert>}
        <TextField label="Имя пользователя" value={username} onChange={(e) => setUsername(e.target.value)} required minLength={3} maxLength={32} pattern="[A-Za-z0-9_]+" autoComplete="username" />
        <TextField label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
        <TextField label="Пароль" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} autoComplete="new-password" />
        <Button type="submit" loading={busy} className="w-full">
          Создать аккаунт
        </Button>
        <p className="text-center text-sm text-zinc-400">
          Уже есть аккаунт?{" "}
          <Link to="/login" className="text-violet-300 hover:text-violet-200">
            Войти
          </Link>
        </p>
        <p className="text-center text-sm text-zinc-400">
          Представляете компанию?{" "}
          <Link to="/register-organization" className="text-violet-300 hover:text-violet-200">
            Зарегистрировать организацию
          </Link>
        </p>
      </form>
    </div>
  );
}
