import Editor from "@monaco-editor/react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { DifficultyBadge, VerdictBadge, VerdictCaption } from "../components/badges";
import { Alert, Button, LoadingBlock, cx } from "../components/ui";
import { languageLabel } from "../lib/format";
import { MONACO_LANGUAGE, TEMPLATES, isTemplate } from "../lib/templates";
import type { Contest, JudgeResult, Language, ProblemDetail, Submission, SystemInfo } from "../types";

const LANGUAGES: Language[] = ["python", "cpp", "java", "javascript"];

export function SolvePage() {
  const params = useParams();
  const problemId = Number(params.problemId);
  const contestId = params.contestId ? Number(params.contestId) : null;
  const { user } = useAuth();
  const [problem, setProblem] = useState<ProblemDetail | null>(null);
  const [contest, setContest] = useState<Contest | null>(null);
  const [language, setLanguage] = useState<Language>("python");
  const [code, setCode] = useState(TEMPLATES.python);
  const [result, setResult] = useState<JudgeResult | null>(null);
  const [history, setHistory] = useState<Submission[]>([]);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedCode, setExpandedCode] = useState("");
  const [busy, setBusy] = useState<"" | "run" | "submit">("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [judgeMode, setJudgeMode] = useState<SystemInfo["judge_mode"] | "">("");

  useEffect(() => {
    api<SystemInfo>("/system")
      .then((info) => setJudgeMode(info.judge_mode))
      .catch(() => setJudgeMode(""));
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    const requests: Promise<void>[] = [
      api<ProblemDetail>(`/problems/${problemId}`)
        .then((item) => {
          if (!cancelled) setProblem(item);
        }),
    ];
    if (contestId) {
      requests.push(
        api<Contest>(`/contests/${contestId}`).then((item) => {
          if (!cancelled) setContest(item);
        }),
      );
    }
    Promise.all(requests)
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Не удалось открыть задачу");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [problemId, contestId]);

  useEffect(() => {
    if (!user) {
      setHistory([]);
      return;
    }
    const params = new URLSearchParams({ problem_id: String(problemId), limit: "15" });
    if (contestId) params.set("contest_id", String(contestId));
    api<Submission[]>(`/submissions?${params.toString()}`)
      .then(setHistory)
      .catch(() => setHistory([]));
  }, [user, problemId, contestId, result]);

  function changeLanguage(next: Language) {
    setCode((current) => (isTemplate(current) ? TEMPLATES[next] : current));
    setLanguage(next);
  }

  const accessReason = submissionBlockReason(user, contest, contestId);
  const blockReason = [
    judgeMode === "unavailable" ? "Проверка кода недоступна: на сервере не задан JUDGE0_URL. Вердикт не выставляется." : "",
    accessReason,
  ]
    .filter(Boolean)
    .join(" ");

  async function judge(kind: "run" | "submit") {
    if (!problem || blockReason) return;
    setBusy(kind);
    setError("");
    try {
      const path = kind === "run" ? "/run" : "/submissions";
      const body = await api<JudgeResult>(path, {
        method: "POST",
        body: JSON.stringify({
          problem_id: problem.id,
          language,
          source_code: code,
          contest_id: contestId,
        }),
      });
      setResult(body);
      if (kind === "submit" && body.verdict === "OK") {
        setProblem((current) => (current ? { ...current, solved_by_me: true } : current));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось проверить код");
    } finally {
      setBusy("");
    }
  }

  async function toggleHistory(id: number) {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    try {
      const full = await api<Submission>(`/submissions/${id}`);
      setExpandedCode(full.source_code ?? "");
      setExpandedId(id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось открыть код");
    }
  }

  if (loading) return <LoadingBlock label="Загрузка условия..." />;
  if (!problem) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <Alert>{error || "Задача не найдена"}</Alert>
      </div>
    );
  }

  return (
    <div className="mx-auto grid max-w-[1400px] gap-4 px-4 py-4 lg:grid-cols-2">
      <article className="card p-5">
        <Link to={contestId ? `/contests/${contestId}` : problem.kind === "production" ? "/production" : "/problems"} className="text-sm text-violet-300 hover:text-violet-200">
          {contestId ? "← К соревнованию" : problem.kind === "production" ? "← Производственные задачи" : "← Все задачи"}
        </Link>
        {contest && <p className="mt-3 text-xs uppercase tracking-wide text-zinc-500">{contest.title}</p>}
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-semibold">{problem.title}</h1>
          <DifficultyBadge value={problem.difficulty} />
          {problem.solved_by_me && <span className="text-xs text-emerald-300">Решено</span>}
        </div>
        <p className="mt-2 text-sm text-zinc-400">{problem.short_description}</p>
        <p className="mt-1 text-xs text-zinc-500">
          {problem.category} · {problem.author_name}
        </p>
        <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-zinc-100">{problem.statement}</p>
        <Section title="Входные данные">{problem.input_format}</Section>
        <Section title="Выходные данные">{problem.output_format}</Section>
        <Section title="Ограничения">{`${problem.constraints}\nВремя: ${problem.time_limit_ms} мс\nПамять: ${problem.memory_limit_mb} МБ`}</Section>
        <h2 className="mb-2 mt-6 text-sm font-medium uppercase tracking-wide text-zinc-500">Примеры</h2>
        <div className="space-y-3">
          {problem.examples.map((example, index) => (
            <div key={index} className="grid gap-2 sm:grid-cols-2">
              <Sample label={`Вход ${index + 1}`} value={example.input} />
              <Sample label={`Выход ${index + 1}`} value={example.output} />
            </div>
          ))}
        </div>
      </article>

      <section className="lg:sticky lg:top-20 lg:self-start">
        <div className="card overflow-hidden">
          <div className="flex flex-wrap items-center gap-2 border-b border-white/10 px-3 py-3">
            <select className="input w-auto" value={language} onChange={(event) => changeLanguage(event.target.value as Language)}>
              {LANGUAGES.map((item) => (
                <option key={item} value={item}>
                  {languageLabel[item]}
                </option>
              ))}
            </select>
            <div className="ml-auto flex gap-2">
              <Button variant="secondary" loading={busy === "run"} disabled={Boolean(blockReason) || busy === "submit"} onClick={() => judge("run")}>
                Запустить
              </Button>
              <Button loading={busy === "submit"} disabled={Boolean(blockReason) || busy === "run"} onClick={() => judge("submit")}>
                Отправить решение
              </Button>
            </div>
          </div>
          {blockReason && <p className="border-b border-white/10 px-3 py-2 text-sm text-amber-100">{blockReason}</p>}
          <Editor
            height="460px"
            language={MONACO_LANGUAGE[language]}
            theme="vs-dark"
            value={code}
            onChange={(value) => setCode(value ?? "")}
            loading={<div className="p-4 text-sm text-zinc-400">Загрузка редактора...</div>}
            options={{
              fontSize: 14,
              fontFamily: "JetBrains Mono, Consolas, monospace",
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              automaticLayout: true,
              tabSize: 4,
              padding: { top: 12, bottom: 12 },
            }}
          />
        </div>
        <div className="mt-3">
          {error && <Alert>{error}</Alert>}
          {result ? <ResultPanel result={result} /> : (
            <p className="px-1 py-3 text-sm text-zinc-500">
              {judgeMode === "unavailable"
                ? "Вердикт появится после подключения Judge0."
                : "Запустите примеры или отправьте решение на полную проверку."}
            </p>
          )}
        </div>
        <div className="mt-4">
          <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-zinc-500">История отправок</h2>
          {!user ? (
            <p className="text-sm text-zinc-500">История появится после входа.</p>
          ) : history.length === 0 ? (
            <p className="text-sm text-zinc-500">Вы ещё не отправляли решение этой задачи.</p>
          ) : (
            <div className="card divide-y divide-white/5">
              {history.map((item) => (
                <div key={item.id}>
                  <button onClick={() => toggleHistory(item.id)} className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-white/[0.03]">
                    <VerdictBadge value={item.verdict} />
                    <span className="text-sm text-zinc-300">{languageLabel[item.language]}</span>
                    <span className="text-xs text-zinc-500">
                      {item.tests_passed}/{item.tests_total}
                      {item.runtime_ms != null ? ` · ${item.runtime_ms} мс` : ""}
                    </span>
                    <span className="ml-auto text-xs text-zinc-500">{new Date(item.created_at).toLocaleString("ru-RU")}</span>
                  </button>
                  {expandedId === item.id && (
                    <pre className="max-h-64 overflow-auto border-t border-white/5 bg-black/30 p-3 font-mono text-xs text-zinc-300">{expandedCode}</pre>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function submissionBlockReason(user: { id: number } | null, contest: Contest | null, contestId: number | null) {
  if (!user) return "Войдите, чтобы запускать и отправлять код.";
  if (!contestId) return "";
  if (!contest) return "Соревнование недоступно.";
  if (!contest.is_registered) return "Зарегистрируйтесь на соревнование, чтобы отправить решение.";
  if (contest.phase === "upcoming") return "Соревнование ещё не началось.";
  if (contest.phase === "finished") return "Соревнование уже завершено.";
  if (contest.phase === "draft") return "Соревнование ещё не опубликовано.";
  return "";
}

function Section({ title, children }: { title: string; children: string }) {
  return (
    <section className="mt-5">
      <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">{title}</h2>
      <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-zinc-200">{children}</p>
    </section>
  );
}

function Sample({ label, value }: { label: string; value: string }) {
  return (
    <div className="overflow-hidden rounded-lg border border-white/10 bg-black/30">
      <div className="border-b border-white/10 px-3 py-1.5 text-xs text-zinc-500">{label}</div>
      <pre className="overflow-x-auto p-3 font-mono text-xs text-zinc-200">{value}</pre>
    </div>
  );
}

function ResultPanel({ result }: { result: JudgeResult }) {
  const ok = result.verdict === "OK";
  return (
    <div className={cx("rounded-xl border p-4", ok ? "border-emerald-500/30 bg-emerald-500/10" : "border-red-500/30 bg-red-500/10")}>
      <div className="flex flex-wrap items-center gap-2">
        <VerdictBadge value={result.verdict} />
        <VerdictCaption value={result.verdict} />
        <span className="rounded-md bg-white/10 px-2 py-0.5 text-xs text-zinc-200">{result.judge_label}</span>
      </div>
      <p className="mt-2 text-sm text-zinc-100">
        {result.samples_only ? "Проверка примеров. " : "Полная проверка. "}
        Тесты: {result.tests_passed}/{result.tests_total}
        {result.runtime_ms != null ? ` · ${result.runtime_ms} мс` : ""}
      </p>
      {result.message && <pre className="mt-3 whitespace-pre-wrap font-mono text-xs text-zinc-200">{result.message}</pre>}
      {result.failed_input != null && (
        <div className="mt-3 grid gap-2">
          <Sample label="Вход неудачного теста" value={result.failed_input} />
          {result.failed_expected != null && <Sample label="Ожидалось" value={result.failed_expected} />}
          {result.failed_actual != null && <Sample label="Получено" value={result.failed_actual} />}
        </div>
      )}
      {!ok && !result.samples_only && result.failed_input == null && result.verdict !== "CE" && (
        <p className="mt-3 text-sm text-zinc-200">Это скрытый тест: вход и ожидаемый ответ не показываются.</p>
      )}
    </div>
  );
}
