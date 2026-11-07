import { FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { PhaseBadge } from "../components/badges";
import { Alert, Button, EmptyState, LoadingBlock, Page, TextArea, TextField } from "../components/ui";
import { formatLabel, phaseLabel } from "../lib/format";
import type { OrganizationCabinet, OrganizationMine } from "../types";

export function OrganizationPage() {
  const { orgId } = useParams();
  if (!orgId) return <OrganizationList />;
  return <OrganizationCabinetView orgId={Number(orgId)} />;
}

function OrganizationList() {
  const [rows, setRows] = useState<OrganizationMine[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<OrganizationMine[]>("/organizations/mine")
      .then(setRows)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Не удалось загрузить организации"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingBlock />;
  return (
    <Page title="Организации" subtitle="Кабинет компании: задачи, турниры и сотрудники.">
      {error && <Alert>{error}</Alert>}
      {rows.length === 0 ? (
        <EmptyState title="Вы не состоите в организации" text="Зарегистрируйте организацию или попросите владельца добавить вас." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {rows.map((organization) => (
            <Link key={organization.id} to={`/organization/${organization.id}`} className="card block p-5 hover:border-violet-500/40">
              <h2 className="font-medium">{organization.name}</h2>
              <p className="mt-2 text-sm text-zinc-400">{organization.description || "Без описания"}</p>
              <p className="mt-3 text-xs text-zinc-500">{organization.member_role === "owner" ? "Владелец" : "Организатор"}</p>
            </Link>
          ))}
        </div>
      )}
    </Page>
  );
}

function OrganizationCabinetView({ orgId }: { orgId: number }) {
  const [org, setOrg] = useState<OrganizationCabinet | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [username, setUsername] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  function apply(next: OrganizationCabinet) {
    setOrg(next);
    setName(next.name);
    setDescription(next.description);
    setLogoUrl(next.logo_url ?? "");
  }

  useEffect(() => {
    api<OrganizationCabinet>(`/organizations/${orgId}`)
      .then(apply)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Кабинет недоступен"))
      .finally(() => setLoading(false));
  }, [orgId]);

  async function saveProfile(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      apply(await api<OrganizationCabinet>(`/organizations/${orgId}`, { method: "PATCH", body: JSON.stringify({ name, description, logo_url: logoUrl }) }));
      setNotice("Профиль сохранён.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось сохранить профиль");
    } finally {
      setBusy(false);
    }
  }

  async function addMember(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      apply(await api<OrganizationCabinet>(`/organizations/${orgId}/members`, { method: "POST", body: JSON.stringify({ username }) }));
      setUsername("");
      setNotice("Сотрудник добавлен с правом организовывать турниры и задачи.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось добавить сотрудника");
    } finally {
      setBusy(false);
    }
  }

  async function removeMember(userId: number) {
    setBusy(true);
    setError("");
    try {
      apply(await api<OrganizationCabinet>(`/organizations/${orgId}/members/${userId}`, { method: "DELETE" }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось удалить сотрудника");
    } finally {
      setBusy(false);
    }
  }

  async function setVisibility(problemId: number, publish: boolean) {
    setError("");
    try {
      await api(`/organizations/${orgId}/problems/${problemId}/${publish ? "publish" : "hide"}`, { method: "POST" });
      apply(await api<OrganizationCabinet>(`/organizations/${orgId}`));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось изменить публикацию");
    }
  }

  if (loading) return <LoadingBlock label="Загрузка кабинета..." />;
  if (!org) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <Alert>{error || "Кабинет недоступен"}</Alert>
      </div>
    );
  }

  return (
    <Page
      title={org.name}
      subtitle={org.description || "Кабинет организации"}
      actions={
        <Link to={`/organization/${org.id}/problems/new`}>
          <Button>Новая задача</Button>
        </Link>
      }
    >
      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {notice && <p className="mb-4 text-sm text-emerald-300">{notice}</p>}
      {org.logo_url && <img src={org.logo_url} alt="" className="mb-4 h-16 w-16 rounded-lg object-cover" />}
      <div className="mb-6 grid gap-3 sm:grid-cols-4">
        <Stat label="Задач" value={String(org.problem_count)} />
        <Stat label="Опубликовано" value={String(org.published_problem_count)} />
        <Stat label="Турниров" value={String(org.contest_count)} />
        <Stat label="Участников" value={String(org.participant_count)} />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <form onSubmit={saveProfile} className="card space-y-4 p-5">
          <h2 className="font-medium">Профиль</h2>
          <TextField label="Название" value={name} onChange={(event) => setName(event.target.value)} required minLength={2} />
          <TextArea label="Описание" value={description} onChange={(event) => setDescription(event.target.value)} rows={4} />
          <TextField label="Ссылка на логотип" value={logoUrl} onChange={(event) => setLogoUrl(event.target.value)} placeholder="https://" />
          <Button type="submit" loading={busy}>
            Сохранить профиль
          </Button>
        </form>
        <section className="card p-5">
          <h2 className="font-medium">Сотрудники</h2>
          <ul className="mt-3 space-y-2 text-sm">
            {org.members.map((member) => (
              <li key={member.user_id} className="flex items-center justify-between gap-3">
                <span>
                  {member.username} <span className="text-zinc-500">{member.member_role === "owner" ? "владелец" : "организатор"}</span>
                </span>
                {org.member_role === "owner" && member.member_role !== "owner" && (
                  <Button variant="ghost" onClick={() => removeMember(member.user_id)} disabled={busy}>
                    Удалить
                  </Button>
                )}
              </li>
            ))}
          </ul>
          {org.member_role === "owner" && (
            <form onSubmit={addMember} className="mt-4 flex gap-2">
              <input className="input" placeholder="Имя пользователя" value={username} onChange={(event) => setUsername(event.target.value)} required />
              <Button type="submit" loading={busy}>
                Добавить
              </Button>
            </form>
          )}
        </section>
      </div>
      <h2 className="mb-3 mt-8 font-medium">Задачи</h2>
      {org.problems.length === 0 ? (
        <EmptyState title="Задач пока нет" text="Создайте алгоритмическую или производственную задачу." />
      ) : (
        <div className="space-y-3">
          {org.problems.map((problem) => (
            <div key={problem.id} className="card flex flex-wrap items-center justify-between gap-3 p-4">
              <div>
                <p className="font-medium">{problem.title}</p>
                <p className="mt-1 text-xs text-zinc-500">
                  {problem.kind === "production" ? "Производственная" : "Алгоритмическая"} · {problem.category} ·{" "}
                  {problem.publication_status === "published" ? "опубликована" : "скрыта"} · {problem.accepted_count} решений
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link to={`/organization/${org.id}/problems/${problem.id}`}>
                  <Button variant="secondary">Изменить</Button>
                </Link>
                <Button variant="ghost" onClick={() => setVisibility(problem.id, problem.publication_status !== "published")}>
                  {problem.publication_status === "published" ? "Скрыть" : "Опубликовать"}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
      <h2 className="mb-3 mt-8 font-medium">Турниры</h2>
      {org.contests.length === 0 ? (
        <EmptyState title="Корпоративных турниров нет" text="При создании соревнования выберите эту организацию." />
      ) : (
        <div className="space-y-3">
          {org.contests.map((contest) => (
            <Link key={contest.id} to={`/contests/${contest.id}`} className="card flex items-center justify-between gap-3 p-4 hover:border-violet-500/40">
              <span>
                <span className="block font-medium">{contest.title}</span>
                <span className="text-xs text-zinc-500">{formatLabel[contest.participation_format]}</span>
              </span>
              <PhaseBadge value={contest.phase} />
            </Link>
          ))}
        </div>
      )}
      <p className="mt-4 text-xs text-zinc-500">Статусы турниров: {Object.values(phaseLabel).join(", ")}.</p>
    </Page>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card p-4">
      <p className="text-xs uppercase tracking-wide text-zinc-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}
