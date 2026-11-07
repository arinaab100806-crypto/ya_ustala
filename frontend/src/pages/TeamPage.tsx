import { FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { Alert, Button, LoadingBlock, Page, TextArea, TextField } from "../components/ui";
import type { Team } from "../types";

export function TeamPage() {
  const { teamId } = useParams();
  const { user } = useAuth();
  const [team, setTeam] = useState<Team | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [specialization, setSpecialization] = useState("");
  const [maxMembers, setMaxMembers] = useState(3);
  const [recruiting, setRecruiting] = useState(true);

  function apply(next: Team) {
    setTeam(next);
    setName(next.name);
    setDescription(next.description);
    setLogoUrl(next.logo_url ?? "");
    setSpecialization(next.specialization);
    setMaxMembers(next.max_members);
    setRecruiting(next.recruiting);
  }

  useEffect(() => {
    api<Team>(`/teams/${teamId}`)
      .then(apply)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Команда не найдена"))
      .finally(() => setLoading(false));
  }, [teamId, user?.id]);

  async function reload() {
    apply(await api<Team>(`/teams/${teamId}`));
  }

  async function applyToTeam() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      apply(await api<Team>(`/teams/${teamId}/applications`, { method: "POST" }));
      setNotice("Заявка отправлена капитану.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось отправить заявку");
    } finally {
      setBusy(false);
    }
  }

  async function decide(applicationId: number, accept: boolean) {
    setBusy(true);
    setError("");
    try {
      apply(await api<Team>(`/teams/${teamId}/applications/${applicationId}/${accept ? "accept" : "reject"}`, { method: "POST" }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось рассмотреть заявку");
    } finally {
      setBusy(false);
    }
  }

  async function remove(userId: number) {
    setBusy(true);
    setError("");
    try {
      apply(await api<Team>(`/teams/${teamId}/members/${userId}`, { method: "DELETE" }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось исключить участника");
    } finally {
      setBusy(false);
    }
  }

  async function leave() {
    setBusy(true);
    setError("");
    try {
      await api(`/teams/mine`, { method: "DELETE" });
      await reload();
      setNotice("Вы вышли из команды.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось выйти из команды");
    } finally {
      setBusy(false);
    }
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      apply(
        await api<Team>(`/teams/${teamId}`, {
          method: "PATCH",
          body: JSON.stringify({ name, description, logo_url: logoUrl, specialization, max_members: maxMembers, recruiting }),
        }),
      );
      setNotice("Данные команды сохранены.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось сохранить команду");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <LoadingBlock />;
  if (!team) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <Alert>{error || "Команда не найдена"}</Alert>
      </div>
    );
  }

  return (
    <Page
      title={team.name}
      subtitle={team.description || "Команда без описания"}
      actions={
        <Link to="/teams">
          <Button variant="secondary">Все команды</Button>
        </Link>
      }
    >
      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {notice && <p className="mb-4 text-sm text-emerald-300">{notice}</p>}
      {team.logo_url && <img src={team.logo_url} alt="" className="mb-4 h-16 w-16 rounded-lg object-cover" />}
      <p className="mb-4 text-sm text-zinc-400">
        {team.specialization} · капитан {team.captain_name} · {team.member_count}/{team.max_members} · {team.recruiting ? "набор открыт" : "набор закрыт"} · решено задач {team.solved_count} · турниров {team.contest_count}
      </p>
      <div className="mb-6 flex flex-wrap gap-2">
        {user && !team.is_member && team.recruiting && team.member_count < team.max_members && (
          <Button loading={busy} onClick={applyToTeam}>
            Подать заявку
          </Button>
        )}
        {team.is_member && !team.is_captain && (
          <Button variant="danger" loading={busy} onClick={leave}>
            Выйти из команды
          </Button>
        )}
      </div>
      <h2 className="mb-3 font-medium">Состав</h2>
      <ul className="card divide-y divide-white/5">
        {team.members.map((member) => (
          <li key={member.user_id} className="flex items-center justify-between px-4 py-3 text-sm">
            <span>
              {member.username} {member.is_captain && <span className="text-zinc-500">капитан</span>}
            </span>
            {team.is_captain && !member.is_captain && (
              <Button variant="ghost" onClick={() => remove(member.user_id)} disabled={busy}>
                Исключить
              </Button>
            )}
          </li>
        ))}
      </ul>
      {team.is_captain && (
        <>
          <h2 className="mb-3 mt-8 font-medium">Заявки</h2>
          {team.applications.length === 0 ? (
            <p className="text-sm text-zinc-400">Входящих заявок нет.</p>
          ) : (
            <ul className="space-y-2">
              {team.applications.map((application) => (
                <li key={application.id} className="card flex items-center justify-between gap-3 p-4 text-sm">
                  <span>{application.username}</span>
                  <span className="flex gap-2">
                    <Button onClick={() => decide(application.id, true)} disabled={busy}>
                      Принять
                    </Button>
                    <Button variant="secondary" onClick={() => decide(application.id, false)} disabled={busy}>
                      Отклонить
                    </Button>
                  </span>
                </li>
              ))}
            </ul>
          )}
          <form onSubmit={save} className="card mt-8 max-w-xl space-y-4 p-5">
            <h2 className="font-medium">Управление</h2>
            <TextField label="Название" value={name} onChange={(event) => setName(event.target.value)} required minLength={2} />
            <TextArea label="Описание" value={description} onChange={(event) => setDescription(event.target.value)} rows={4} />
            <TextField label="Ссылка на логотип" value={logoUrl} onChange={(event) => setLogoUrl(event.target.value)} placeholder="https://" />
            <TextField label="Специализация" value={specialization} onChange={(event) => setSpecialization(event.target.value)} required />
            <TextField label="Максимум участников" type="number" min={team.member_count} max={10} value={maxMembers} onChange={(event) => setMaxMembers(Number(event.target.value))} required />
            <label className="flex items-center gap-2 text-sm text-zinc-300">
              <input type="checkbox" checked={recruiting} onChange={(event) => setRecruiting(event.target.checked)} />
              Набор открыт
            </label>
            <Button type="submit" loading={busy}>
              Сохранить
            </Button>
          </form>
        </>
      )}
    </Page>
  );
}
