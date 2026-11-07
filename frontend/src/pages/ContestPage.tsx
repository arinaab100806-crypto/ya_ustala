import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { DifficultyBadge, PhaseBadge, VerdictBadge } from "../components/badges";
import { Alert, Button, EmptyState, LoadingBlock, Page, cx } from "../components/ui";
import { formatDate, formatDuration, formatLabel, formatPenalty, languageLabel } from "../lib/format";
import type { Contest, Standing, Submission, Team } from "../types";

type Tab = "tasks" | "standings" | "about";

export function ContestPage() {
  const { contestId } = useParams();
  const { user } = useAuth();
  const [contest, setContest] = useState<Contest | null>(null);
  const [tab, setTab] = useState<Tab>("tasks");
  const [standings, setStandings] = useState<Standing[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [myTeam, setMyTeam] = useState<Team | null>(null);

  async function loadContest() {
    const data = await api<Contest>(`/contests/${contestId}`);
    setContest(data);
    return data;
  }

  useEffect(() => {
    setLoading(true);
    loadContest()
      .then(() => setError(""))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Соревнование не найдено"))
      .finally(() => setLoading(false));
  }, [contestId, user?.id]);

  useEffect(() => {
    if (!user) {
      setMyTeam(null);
      return;
    }
    api<Team | null>("/teams/mine")
      .then(setMyTeam)
      .catch(() => setMyTeam(null));
  }, [user]);

  useEffect(() => {
    if (!contest) return;
    let stop = false;
    async function loadStandings() {
      try {
        const rows = await api<Standing[]>(`/contests/${contestId}/standings`);
        if (!stop) setStandings(rows);
      } catch (err) {
        if (!stop) setActionError(err instanceof ApiError ? err.message : "Не удалось загрузить таблицу");
      }
    }
    if (tab === "standings") {
      loadStandings();
      const timer = contest.phase === "running" ? window.setInterval(loadStandings, 15000) : undefined;
      return () => {
        stop = true;
        if (timer) window.clearInterval(timer);
      };
    }
    if (tab === "about" && user) {
      api<Submission[]>(`/submissions?contest_id=${contestId}&limit=20`)
        .then((rows) => {
          if (!stop) setSubmissions(rows);
        })
        .catch(() => {
          if (!stop) setSubmissions([]);
        });
    }
    return () => {
      stop = true;
    };
  }, [tab, contest, contestId, user]);

  async function changeRegistration(join: boolean) {
    setBusy(true);
    setActionError("");
    try {
      const path = join && contest?.participation_format === "team" ? `/contests/${contestId}/register-team` : `/contests/${contestId}/register`;
      const updated = await api<Contest>(path, { method: join ? "POST" : "DELETE" });
      setContest(updated);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Не удалось изменить регистрацию");
    } finally {
      setBusy(false);
    }
  }

  async function publish() {
    setBusy(true);
    setActionError("");
    try {
      const updated = await api<Contest>(`/contests/${contestId}/publish`, { method: "POST" });
      setContest(updated);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Не удалось опубликовать");
    } finally {
      setBusy(false);
    }
  }

  async function finish() {
    setBusy(true);
    setActionError("");
    try {
      const updated = await api<Contest>(`/contests/${contestId}/finish`, { method: "POST" });
      setContest(updated);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Не удалось завершить соревнование");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <LoadingBlock label="Загрузка соревнования..." />;
  if (!contest) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <Alert>{error || "Соревнование не найдено"}</Alert>
      </div>
    );
  }

  const canRegister = user && contest.participation_format === "individual" && contest.phase !== "finished" && contest.phase !== "draft" && !contest.is_registered;
  const canRegisterTeam = user && contest.participation_format === "team" && contest.phase !== "finished" && contest.phase !== "draft" && myTeam?.is_captain && !contest.is_registered;
  const canLeave = user && contest.is_registered && contest.phase === "upcoming" && (contest.participation_format === "individual" || myTeam?.is_captain);

  return (
    <Page
      title={contest.title}
      subtitle={contest.description}
      actions={
        <div className="flex flex-wrap gap-2">
          {contest.is_owner && contest.phase !== "running" && contest.phase !== "finished" && (
            <Link to={`/contests/${contest.id}/edit`}>
              <Button variant="secondary">Редактировать</Button>
            </Link>
          )}
          {contest.is_owner && contest.phase === "draft" && (
            <Button loading={busy} onClick={publish}>
              Опубликовать
            </Button>
          )}
          {contest.is_owner && contest.phase === "running" && (
            <Button variant="danger" loading={busy} onClick={finish}>
              Завершить
            </Button>
          )}
          {(contest.is_owner || (contest.organization_id != null && user?.organizations.some((item) => item.organization_id === contest.organization_id))) && (
            <Link to={`/contests/${contest.id}/fairplay`}>
              <Button variant="secondary">Проверка ответов</Button>
            </Link>
          )}
          {contest.phase === "finished" && (contest.is_owner || (contest.organization_id != null && user?.organizations.some((item) => item.organization_id === contest.organization_id))) && (
            <Link to={`/contests/${contest.id}/reports`}>
              <Button variant="secondary">Отчёт</Button>
            </Link>
          )}
          {canRegister && (
            <Button loading={busy} onClick={() => changeRegistration(true)}>
              Зарегистрироваться
            </Button>
          )}
          {canRegisterTeam && (
            <Button loading={busy} onClick={() => changeRegistration(true)}>
              Записать команду
            </Button>
          )}
          {canLeave && (
            <Button variant="danger" loading={busy} onClick={() => changeRegistration(false)}>
              {contest.participation_format === "team" ? "Снять команду" : "Отменить регистрацию"}
            </Button>
          )}
        </div>
      }
    >
      <div className="mb-4 flex flex-wrap items-center gap-3 text-sm text-zinc-400">
        <PhaseBadge value={contest.phase} />
        <span>{formatLabel[contest.participation_format]}</span>
        <span>{contest.problem_count} задач</span>
        <span>{contest.participant_count} участников</span>
        <span>{formatDuration(contest.duration_minutes)}</span>
        <span>Старт {formatDate(contest.start_time)}</span>
        <span>Организатор {contest.organizer_name}</span>
        {contest.organization_name && <span>Организация {contest.organization_name}</span>}
        {contest.is_registered && <span className="text-emerald-300">Вы зарегистрированы</span>}
      </div>
      {actionError && (
        <div className="mb-4">
          <Alert>{actionError}</Alert>
        </div>
      )}
      {contest.participation_format === "team" && contest.phase !== "draft" && contest.phase !== "finished" && !contest.is_registered && (
        <p className="mb-4 text-sm text-zinc-400">
          {myTeam?.is_captain
            ? `Капитан может записать команду «${myTeam.name}». В таблицу попадёт общий результат участников.`
            : myTeam
              ? "Команду записывает капитан."
              : "Чтобы участвовать, создайте команду или вступите в неё. Личная регистрация закрыта."}
        </p>
      )}
      {!user && contest.participation_format === "individual" && contest.phase !== "draft" && contest.phase !== "finished" && (
        <p className="mb-4 text-sm text-zinc-400">
          <Link to="/login" className="text-violet-300">
            Войдите
          </Link>
          , чтобы зарегистрироваться.
        </p>
      )}
      <div className="mb-4 flex gap-2">
        {(
          [
            ["tasks", "Задачи"],
            ["standings", "Результаты"],
            ["about", "Мои отправки"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={cx("rounded-lg px-3 py-1.5 text-sm", tab === id ? "bg-white/10 text-white" : "text-zinc-400 hover:text-white")}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "tasks" && (
        <div className="card overflow-hidden">
          {contest.problems.length === 0 ? (
            <EmptyState title="В соревновании нет задач" text="Организатор ещё не добавил задачи." />
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="border-b border-white/10 text-xs uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-4 py-3 font-medium">#</th>
                  <th className="px-4 py-3 font-medium">Задача</th>
                  <th className="px-4 py-3 font-medium">Сложность</th>
                  <th className="px-4 py-3 font-medium" />
                </tr>
              </thead>
              <tbody>
                {contest.problems.map((problem) => (
                  <tr key={problem.problem_id} className="border-b border-white/5 last:border-0">
                    <td className="px-4 py-3 font-mono text-zinc-400">{problem.code}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-2">
                        <span className={cx("h-2 w-2 rounded-full", problem.solved_by_me ? "bg-emerald-400" : "bg-zinc-700")} />
                        {problem.title}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <DifficultyBadge value={problem.difficulty} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link to={`/contests/${contest.id}/problems/${problem.problem_id}`} className="text-violet-300 hover:text-violet-200">
                        Решать
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="border-t border-white/10 px-4 py-3 text-xs text-zinc-500">
            В зачёт идут только отправки со страницы соревнования. За каждую решённую задачу начисляется один балл, при равенстве выше участник с меньшим суммарным временем.
          </p>
        </div>
      )}

      {tab === "standings" && (
        <div className="card overflow-hidden">
          {standings.length === 0 ? (
            <EmptyState title="Таблица пуста" text="Участники появятся здесь после регистрации." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="border-b border-white/10 text-xs uppercase tracking-wide text-zinc-500">
                  <tr>
                    <th className="px-4 py-3 font-medium">Место</th>
                    <th className="px-4 py-3 font-medium">{contest.participation_format === "team" ? "Команда" : "Имя пользователя"}</th>
                    <th className="px-4 py-3 font-medium">Решено</th>
                    <th className="px-4 py-3 font-medium">Время</th>
                  </tr>
                </thead>
                <tbody>
                  {standings.map((row) => (
                    <tr key={row.team_id ?? row.user_id} className={cx("border-b border-white/5 last:border-0", (user?.username === row.username || myTeam?.name === row.username) && "bg-violet-500/10")}>
                      <td className="px-4 py-3">{row.place}</td>
                      <td className="px-4 py-3">{row.username}</td>
                      <td className="px-4 py-3">
                        {row.solved} / {contest.problem_count}
                      </td>
                      <td className="px-4 py-3 font-mono text-zinc-300">{row.solved ? formatPenalty(row.time_seconds) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {contest.phase === "running" && <p className="border-t border-white/10 px-4 py-3 text-xs text-zinc-500">Таблица обновляется автоматически.</p>}
        </div>
      )}

      {tab === "about" && (
        <div>
          {!user ? (
            <EmptyState title="Войдите в аккаунт" text="Тогда здесь появятся ваши отправки в этом соревновании." />
          ) : submissions.length === 0 ? (
            <EmptyState title="Отправок пока нет" text="Откройте задачу соревнования и отправьте решение." />
          ) : (
            <div className="card divide-y divide-white/5">
              {submissions.map((submission) => (
                <Link key={submission.id} to={`/contests/${contest.id}/problems/${submission.problem_id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-white/[0.03]">
                  <VerdictBadge value={submission.verdict} />
                  <div>
                    <p className="text-sm">{submission.problem_title}</p>
                    <p className="text-xs text-zinc-500">
                      {languageLabel[submission.language]} · {formatDate(submission.created_at)}
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
    </Page>
  );
}
