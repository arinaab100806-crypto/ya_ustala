import Editor from "@monaco-editor/react";
import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { Alert, Button, LoadingBlock, Page } from "../components/ui";
import { MONACO_LANGUAGE, TEMPLATES } from "../lib/templates";
import type { Language, Problem } from "../types";

interface ArenaTask {
  problem_id: number;
  title: string;
  order_index: number;
  assignee_role: number | null;
}

interface ArenaPlayer {
  slot: number;
  user_id: number | null;
  username: string | null;
  team_index: number;
  role: number;
  stage: "coding" | "fixing";
  problem_id: number | null;
  times: Array<{ problem_id: number; seconds: number | null }>;
}

interface ArenaMatch {
  id: number;
  mode: "duel" | "team";
  status: "waiting" | "live" | "finished";
  invite_code: string;
  organizer_id: number;
  winner_name: string | null;
  elapsed_seconds: number;
  my_slot: number | null;
  tasks: ArenaTask[];
  players: ArenaPlayer[];
}

const STAGE_LABEL = {
  coding: "1. Написание кода",
  fixing: "2. Правка ответа",
};

function clock(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}:${rest.toString().padStart(2, "0")}`;
}

function Trophy() {
  return (
    <svg viewBox="0 0 64 64" className="mx-auto h-24 w-24" aria-hidden="true">
      <path d="M18 10h28v8c0 10-6 18-14 20-8-2-14-10-14-20V10z" fill="#f5c542" />
      <path d="M18 14H10c0 8 4 12 8 14M46 14h8c0 8-4 12-8 14" fill="none" stroke="#f5c542" strokeWidth="4" />
      <path d="M28 38h8v6h-8zM22 48h20v4H22z" fill="#e8b931" />
    </svg>
  );
}

export function ArenaLobbyPage() {
  const navigate = useNavigate();
  const [problems, setProblems] = useState<Problem[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [roles, setRoles] = useState<Record<number, number>>({});
  const [mode, setMode] = useState<"duel" | "team">("duel");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [searching, setSearching] = useState(false);
  const [busy, setBusy] = useState(false);
  const [invite, setInvite] = useState("");

  useEffect(() => {
    api<Problem[]>("/problems")
      .then((rows) => {
        setProblems(rows);
        setSelected(rows.slice(0, 2).map((problem) => problem.id));
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Не удалось загрузить задачи"));
    api<{ match: ArenaMatch | null }>("/matches/current")
      .then((data) => {
        if (data.match) navigate(`/play/${data.match.id}`);
      })
      .catch(() => undefined);
  }, [navigate]);

  useEffect(() => {
    if (!searching) return undefined;
    const timer = window.setInterval(() => {
      api<{ match: ArenaMatch | null }>("/matches/current")
        .then((data) => {
          if (data.match) navigate(`/play/${data.match.id}`);
        })
        .catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [searching, navigate]);

  function toggle(problemId: number) {
    setSelected((current) => (current.includes(problemId) ? current.filter((id) => id !== problemId) : [...current, problemId]));
  }

  async function queue(nextMode: "duel" | "team") {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api<{ state: string; match: ArenaMatch | null; waiting_count: number; needed: number }>("/matches/queue", {
        method: "POST",
        body: JSON.stringify({ mode: nextMode }),
      });
      if (result.match) {
        navigate(`/play/${result.match.id}`);
        return;
      }
      setSearching(true);
      setNotice(`Ищем ${nextMode === "duel" ? "соперника" : "участников"}: ${result.waiting_count} из ${result.needed}.`);
    } catch (err) {
      setSearching(false);
      setError(err instanceof ApiError ? err.message : "Не удалось встать в очередь");
    } finally {
      setBusy(false);
    }
  }

  async function createRoom(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const match = await api<ArenaMatch>("/matches", {
        method: "POST",
        body: JSON.stringify({
          mode,
          tasks: selected.map((problemId) => ({ problem_id: problemId, assignee_role: mode === "team" ? roles[problemId] ?? 0 : null })),
        }),
      });
      setInvite(`${window.location.origin}/play/join/${match.invite_code}`);
      navigate(`/play/${match.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось создать матч");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Page title="Матчи" subtitle="Дуэль 1×1 и командный матч 2×2 проходят здесь. Соперника или напарника можно найти автоматически либо пригласить по ссылке.">
      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {notice && (
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <p className="text-sm text-emerald-300">{notice}</p>
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              api("/matches/queue", { method: "DELETE" })
                .then(() => {
                  setSearching(false);
                  setNotice("");
                })
                .catch((err) => setError(err instanceof ApiError ? err.message : "Не удалось выйти из очереди"));
            }}
          >
            Отменить поиск
          </Button>
        </div>
      )}
      <div className="mb-8 grid gap-4 md:grid-cols-2">
        <section className="card p-5">
          <h2 className="text-lg font-medium">Режим 1. Дуэль 1×1</h2>
          <p className="mt-2 text-sm text-zinc-400">Два участника решают одни и те же задачи и видят время и этап решения соперника. Когда один закрывает все задачи, матч останавливается.</p>
          <Button className="mt-4" loading={busy} onClick={() => queue("duel")}>
            Найти соперника
          </Button>
        </section>
        <section className="card p-5">
          <h2 className="text-lg font-medium">Режим 2. Команды 2×2</h2>
          <p className="mt-2 text-sm text-zinc-400">Две пары решают общий набор. Порядок задач и то, кто какую задачу берёт, задаёт организатор комнаты.</p>
          <Button className="mt-4" loading={busy} onClick={() => queue("team")}>
            Найти напарников
          </Button>
        </section>
      </div>
      <form onSubmit={createRoom} className="card space-y-4 p-5">
        <h2 className="font-medium">Комната по ссылке</h2>
        <div className="flex gap-2">
          <Button type="button" variant={mode === "duel" ? "primary" : "secondary"} onClick={() => setMode("duel")}>
            Дуэль
          </Button>
          <Button type="button" variant={mode === "team" ? "primary" : "secondary"} onClick={() => setMode("team")}>
            Команды 2×2
          </Button>
        </div>
        <div className="space-y-2">
          {problems.slice(0, 8).map((problem) => (
            <label key={problem.id} className="flex flex-wrap items-center gap-3 text-sm">
              <input type="checkbox" checked={selected.includes(problem.id)} onChange={() => toggle(problem.id)} />
              <span>{problem.title}</span>
              {mode === "team" && selected.includes(problem.id) && (
                <select
                  className="input max-w-[180px] py-1"
                  value={roles[problem.id] ?? 0}
                  onChange={(event) => setRoles((current) => ({ ...current, [problem.id]: Number(event.target.value) }))}
                >
                  <option value={0}>Участник 1</option>
                  <option value={1}>Участник 2</option>
                </select>
              )}
            </label>
          ))}
        </div>
        <Button type="submit" loading={busy}>
          Создать и получить ссылку
        </Button>
        {invite && <p className="text-sm text-zinc-300">{invite}</p>}
      </form>
    </Page>
  );
}

export function ArenaJoinPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const [error, setError] = useState("");

  useEffect(() => {
    api<ArenaMatch>(`/matches/join/${code}`, { method: "POST" })
      .then((match) => navigate(`/play/${match.id}`, { replace: true }))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Не удалось принять приглашение"));
  }, [code, navigate]);

  if (error) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <Alert>{error}</Alert>
      </div>
    );
  }
  return <LoadingBlock label="Вход в матч..." />;
}

export function ArenaRoomPage() {
  const { matchId } = useParams();
  const [match, setMatch] = useState<ArenaMatch | null>(null);
  const [error, setError] = useState("");
  const [problemId, setProblemId] = useState<number | null>(null);
  const [language, setLanguage] = useState<Language>("python");
  const [code, setCode] = useState(TEMPLATES.python);
  const [stage, setStage] = useState<"coding" | "fixing">("coding");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let stop = false;
    async function pull() {
      try {
        const data = await api<ArenaMatch>(`/matches/${matchId}`);
        if (stop) return;
        setMatch(data);
        setProblemId((current) => current ?? data.tasks[0]?.problem_id ?? null);
      } catch (err) {
        if (!stop) setError(err instanceof ApiError ? err.message : "Матч недоступен");
      }
    }
    pull();
    const timer = window.setInterval(pull, 2000);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, [matchId]);

  useEffect(() => {
    if (!match || match.status !== "live" || problemId == null) return;
    api(`/matches/${match.id}/presence`, { method: "POST", body: JSON.stringify({ problem_id: problemId, stage }) }).catch(() => undefined);
  }, [match?.id, match?.status, problemId, stage]);

  async function submit() {
    if (!match || problemId == null) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api<{ verdict: string }>(`/submissions`, {
        method: "POST",
        body: JSON.stringify({ problem_id: problemId, language, source_code: code, match_id: match.id }),
      });
      if (result.verdict === "OK") {
        setStage("coding");
        setNotice("Задача решена верно.");
      } else {
        setStage("fixing");
        setNotice("Ответ не принят. Этап сменился на правку.");
      }
      setMatch(await api<ArenaMatch>(`/matches/${match.id}`));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось отправить решение");
    } finally {
      setBusy(false);
    }
  }

  if (!match && !error) return <LoadingBlock label="Загрузка матча..." />;
  if (!match) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <Alert>{error || "Матч не найден"}</Alert>
      </div>
    );
  }

  const inviteLink = `${window.location.origin}/play/join/${match.invite_code}`;
  const me = match.players.find((player) => player.slot === match.my_slot);

  return (
    <Page
      title={match.mode === "duel" ? "Дуэль 1×1" : "Командный матч 2×2"}
      subtitle={match.status === "waiting" ? "Матч начнётся, когда займут все места." : `Время матча ${clock(match.elapsed_seconds)}`}
      actions={
        <Link to="/play">
          <Button variant="secondary">К матчам</Button>
        </Link>
      }
    >
      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {notice && <p className="mb-4 text-sm text-emerald-300">{notice}</p>}
      {match.status === "waiting" && (
        <p className="mb-4 text-sm text-zinc-300">
          Ссылка-приглашение: <span className="text-white">{inviteLink}</span>
        </p>
      )}
      {match.status === "finished" && match.winner_name && (
        <div className="card mb-6 px-6 py-10 text-center">
          <Trophy />
          <p className="mt-4 text-3xl font-semibold text-white">{match.winner_name}</p>
          <p className="mt-1 text-sm text-amber-200">Победитель</p>
        </div>
      )}
      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        {[0, 1].map((teamIndex) => {
          const group = match.players.filter((player) => (match.mode === "duel" ? player.slot === teamIndex : player.team_index === teamIndex));
          if (match.mode === "duel" && teamIndex > 1) return null;
          return (
            <section key={teamIndex} className="card p-4">
              <h2 className="mb-3 font-medium">{match.mode === "duel" ? (teamIndex === match.my_slot ? "Вы" : "Соперник") : teamIndex === 0 ? "Команда 1" : "Команда 2"}</h2>
              <ul className="space-y-3">
                {group.map((player) => (
                  <li key={player.slot} className="rounded-lg border border-white/10 p-3 text-sm">
                    <p className="font-medium">{player.username || `Место ${player.slot + 1} свободно`}</p>
                    {player.username && (
                      <p className="mt-1 text-zinc-400">
                        {STAGE_LABEL[player.stage]}
                        {player.times.some((item) => item.seconds != null) && ` · решено за ${player.times.filter((item) => item.seconds != null).map((item) => clock(item.seconds || 0)).join(", ")}`}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        {match.tasks.map((task, index) => (
          <button
            key={task.problem_id}
            type="button"
            className={`rounded-lg border px-3 py-2 text-sm ${problemId === task.problem_id ? "border-violet-400 bg-violet-500/20" : "border-white/10"}`}
            onClick={() => {
              setProblemId(task.problem_id);
              setStage("coding");
            }}
          >
            {index + 1}. {task.title}
            {task.assignee_role != null ? ` · участник ${task.assignee_role + 1}` : ""}
          </button>
        ))}
      </div>
      {match.status === "live" && me && (
        <div className="card overflow-hidden">
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3 text-sm text-zinc-400">
            <span>{STAGE_LABEL[stage]}</span>
            <select className="input max-w-[160px] py-1" value={language} onChange={(event) => setLanguage(event.target.value as Language)}>
              <option value="python">Python</option>
              <option value="cpp">C++</option>
              <option value="java">Java</option>
              <option value="javascript">JavaScript</option>
            </select>
          </div>
          <Editor
            height="320px"
            language={MONACO_LANGUAGE[language]}
            theme="vs-dark"
            value={code}
            onChange={(value) => {
              setCode(value || "");
              setStage((current) => (current === "fixing" ? "fixing" : "coding"));
            }}
            options={{ minimap: { enabled: false }, fontSize: 14 }}
          />
          <div className="border-t border-white/10 p-4">
            <Button loading={busy} onClick={submit}>
              Отправить решение
            </Button>
          </div>
        </div>
      )}
    </Page>
  );
}
