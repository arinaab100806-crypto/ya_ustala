import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { Alert, Button, EmptyState, LoadingBlock, Page, TextArea, TextField, cx } from "../components/ui";
import type { Team, TeamCard } from "../types";

export function TeamsPage() {
  const { user } = useAuth();
  const [teams, setTeams] = useState<TeamCard[]>([]);
  const [mine, setMine] = useState<Team | null>(null);
  const [search, setSearch] = useState("");
  const [specialization, setSpecialization] = useState("");
  const [recruiting, setRecruiting] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) {
      setMine(null);
      return;
    }
    api<Team | null>("/teams/mine")
      .then(setMine)
      .catch(() => setMine(null));
  }, [user]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (specialization.trim()) params.set("specialization", specialization.trim());
      if (recruiting) params.set("recruiting", recruiting);
      setLoading(true);
      api<TeamCard[]>(`/teams?${params.toString()}`)
        .then((rows) => {
          setTeams(rows);
          setError("");
        })
        .catch((err) => setError(err instanceof ApiError ? err.message : "Не удалось загрузить команды"))
        .finally(() => setLoading(false));
    }, 200);
    return () => window.clearTimeout(timer);
  }, [search, specialization, recruiting]);

  return (
    <Page
      title="Команды"
      subtitle="Найдите команду или создайте свою. Участник состоит только в одной команде."
      actions={
        user && !mine ? (
          <Link to="/teams/new">
            <Button>Создать команду</Button>
          </Link>
        ) : mine ? (
          <Link to={`/teams/${mine.id}`}>
            <Button variant="secondary">Моя команда</Button>
          </Link>
        ) : undefined
      }
    >
      <div className="mb-4 flex flex-col gap-3 sm:flex-row">
        <input className="input sm:max-w-xs" placeholder="Название" value={search} onChange={(event) => setSearch(event.target.value)} />
        <input className="input sm:max-w-xs" placeholder="Специализация" value={specialization} onChange={(event) => setSpecialization(event.target.value)} />
        <select className="input sm:max-w-[180px]" value={recruiting} onChange={(event) => setRecruiting(event.target.value)}>
          <option value="">Любой набор</option>
          <option value="open">Набор открыт</option>
          <option value="closed">Набор закрыт</option>
        </select>
      </div>
      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {loading ? (
        <LoadingBlock label="Загрузка команд..." />
      ) : teams.length === 0 ? (
        <EmptyState title="Команд не найдено" text="Измените поиск или создайте новую команду." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {teams.map((team) => (
            <Link key={team.id} to={`/teams/${team.id}`} className="card block p-5 hover:border-violet-500/40">
              <div className="flex items-start justify-between gap-3">
                <h2 className="font-medium">{team.name}</h2>
                <span className={cx("text-xs", team.recruiting ? "text-emerald-300" : "text-zinc-500")}>{team.recruiting ? "Набор открыт" : "Набор закрыт"}</span>
              </div>
              <p className="mt-2 line-clamp-2 text-sm text-zinc-400">{team.description || "Без описания"}</p>
              <p className="mt-3 text-xs text-zinc-500">
                {team.specialization} · {team.member_count}/{team.max_members} · капитан {team.captain_name}
              </p>
            </Link>
          ))}
        </div>
      )}
    </Page>
  );
}

export function TeamCreatePage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [specialization, setSpecialization] = useState("");
  const [maxMembers, setMaxMembers] = useState(3);
  const [recruiting, setRecruiting] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const team = await api<Team>("/teams", {
        method: "POST",
        body: JSON.stringify({
          name,
          description,
          logo_url: logoUrl,
          specialization,
          max_members: maxMembers,
          recruiting,
        }),
      });
      navigate(`/teams/${team.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось создать команду");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Page title="Новая команда" subtitle="Вы станете капитаном. Покинуть команду капитан не может.">
      <form onSubmit={onSubmit} className="card max-w-xl space-y-4 p-5">
        {error && <Alert>{error}</Alert>}
        <TextField label="Название" value={name} onChange={(event) => setName(event.target.value)} required minLength={2} />
        <TextArea label="Описание" value={description} onChange={(event) => setDescription(event.target.value)} rows={4} />
        <TextField label="Ссылка на логотип" value={logoUrl} onChange={(event) => setLogoUrl(event.target.value)} placeholder="https://" />
        <TextField label="Специализация" value={specialization} onChange={(event) => setSpecialization(event.target.value)} required minLength={2} />
        <TextField label="Максимум участников" type="number" min={2} max={10} value={maxMembers} onChange={(event) => setMaxMembers(Number(event.target.value))} required />
        <label className="flex items-center gap-2 text-sm text-zinc-300">
          <input type="checkbox" checked={recruiting} onChange={(event) => setRecruiting(event.target.checked)} />
          Набор открыт
        </label>
        <Button type="submit" loading={busy}>
          Создать
        </Button>
      </form>
    </Page>
  );
}
