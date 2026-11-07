import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { Alert, Button, EmptyState, LoadingBlock, Page } from "../components/ui";
import { formatDate } from "../lib/format";
import type { FairPlayDetail, FairPlayOverview } from "../types";

const STATUS_LABEL = {
  clear: "Нарушений не обнаружено",
  attention: "Требует внимания",
  reviewed: "Проверено организатором",
};

function mergeSpans(spans: Array<{ start: number; end: number }>, limit: number) {
  const sorted = spans
    .filter((span) => span.end > span.start && span.start >= 0 && span.end <= limit)
    .sort((left, right) => left.start - right.start);
  const merged: Array<{ start: number; end: number }> = [];
  for (const span of sorted) {
    const last = merged[merged.length - 1];
    if (last && span.start <= last.end) last.end = Math.max(last.end, span.end);
    else merged.push({ ...span });
  }
  return merged;
}

function CodeView({ code, fragments }: { code: string; fragments: Array<{ start: number; end: number }> }) {
  const parts: Array<{ text: string; mark: boolean }> = [];
  let cursor = 0;
  for (const span of mergeSpans(fragments, code.length)) {
    if (span.start > cursor) parts.push({ text: code.slice(cursor, span.start), mark: false });
    parts.push({ text: code.slice(span.start, span.end), mark: true });
    cursor = span.end;
  }
  if (cursor < code.length) parts.push({ text: code.slice(cursor), mark: false });
  return (
    <pre className="max-h-[480px] overflow-auto whitespace-pre-wrap rounded-lg bg-black/40 p-3 font-mono text-xs leading-5 text-zinc-200">
      {parts.map((part, index) =>
        part.mark ? (
          <mark key={index} className="rounded bg-amber-400/30 text-amber-100">
            {part.text}
          </mark>
        ) : (
          <span key={index}>{part.text}</span>
        ),
      )}
    </pre>
  );
}

export function FairPlayPage() {
  const { contestId } = useParams();
  const [overview, setOverview] = useState<FairPlayOverview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  function load() {
    setLoading(true);
    api<FairPlayOverview>(`/contests/${contestId}/fairplay`)
      .then((data) => {
        setOverview(data);
        setError("");
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Не удалось открыть проверку ответов"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, [contestId]);

  async function analyze() {
    setBusy(true);
    setError("");
    try {
      setOverview(await api<FairPlayOverview>(`/contests/${contestId}/fairplay`, { method: "POST" }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось сравнить решения");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <LoadingBlock label="Загрузка проверки ответов..." />;
  if (!overview) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <Alert>{error || "Проверка ответов недоступна"}</Alert>
      </div>
    );
  }

  return (
    <Page
      title="Проверка ответов"
      subtitle="Сравнение решений помогает заметить похожий код. Таблица результатов от этого не меняется, решение остаётся за организатором."
      actions={
        <div className="flex flex-wrap gap-2">
          <Link to={`/contests/${contestId}`}>
            <Button variant="secondary">К турниру</Button>
          </Link>
          <Button loading={busy} onClick={analyze}>
            {overview.analyzed_at ? "Повторить анализ" : "Запустить анализ"}
          </Button>
        </div>
      }
    >
      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {!overview.analyzed_at ? (
        <EmptyState title="Анализ не проводился" text="Запустите сравнение, чтобы найти похожие решения. До этого совпадения не считаются ни найденными, ни отсутствующими." />
      ) : (
        <>
          <p className="mb-4 text-sm text-zinc-400">
            Проверено {formatDate(overview.analyzed_at)}. Повторный анализ заменяет прежние отметки «проверено».
          </p>
          {overview.reports.length === 0 ? (
            <p className="mb-6 text-sm text-emerald-300">Подозрительных совпадений не найдено.</p>
          ) : (
            <div className="mb-8 space-y-3">
              {overview.reports.map((report) => (
                <Link key={report.id} to={`/contests/${contestId}/fairplay/${report.id}`} className="card block p-4 hover:border-violet-500/40">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium">
                      {report.username} и {report.matched_username}
                    </p>
                    <span className="text-sm text-amber-200">{report.similarity_percent}%</span>
                  </div>
                  <p className="mt-1 text-sm text-zinc-400">
                    {report.problem_title} · {STATUS_LABEL[report.status]}
                  </p>
                </Link>
              ))}
            </div>
          )}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-b border-white/10 text-xs uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-3 py-2 font-medium">Участник</th>
                  <th className="px-3 py-2 font-medium">Отправки</th>
                  <th className="px-3 py-2 font-medium">Успешные</th>
                  <th className="px-3 py-2 font-medium">Совпадения</th>
                  <th className="px-3 py-2 font-medium">Задачи</th>
                  <th className="px-3 py-2 font-medium">С кем</th>
                  <th className="px-3 py-2 font-medium">Сходство</th>
                  <th className="px-3 py-2 font-medium">Статус</th>
                </tr>
              </thead>
              <tbody>
                {overview.participants.map((person) => (
                  <tr key={person.user_id} className="border-b border-white/5 last:border-0">
                    <td className="px-3 py-3">{person.username}</td>
                    <td className="px-3 py-3">{person.submission_count}</td>
                    <td className="px-3 py-3">{person.solved_count}</td>
                    <td className="px-3 py-3">{person.match_count}</td>
                    <td className="px-3 py-3">{person.problem_titles.join(", ") || "—"}</td>
                    <td className="px-3 py-3">{person.matched_usernames.join(", ") || "—"}</td>
                    <td className="px-3 py-3">{person.max_similarity == null ? "—" : `${person.max_similarity}%`}</td>
                    <td className="px-3 py-3">{STATUS_LABEL[person.status]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Page>
  );
}

export function FairPlayReportPage() {
  const { contestId, reportId } = useParams();
  const [report, setReport] = useState<FairPlayDetail | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<FairPlayDetail>(`/contests/${contestId}/fairplay/reports/${reportId}`)
      .then(setReport)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Отчёт не найден"))
      .finally(() => setLoading(false));
  }, [contestId, reportId]);

  async function review() {
    setBusy(true);
    setError("");
    try {
      setReport(await api<FairPlayDetail>(`/contests/${contestId}/fairplay/reports/${reportId}/review`, { method: "POST" }));
      setNotice("Отчёт отмечен как проверенный. Результат турнира не изменился.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось сохранить отметку");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <LoadingBlock label="Загрузка отчёта..." />;
  if (!report) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <Alert>{error || "Отчёт не найден"}</Alert>
      </div>
    );
  }

  return (
    <Page
      title={`${report.username} и ${report.matched_username}`}
      subtitle={`${report.problem_title} · сходство ${report.similarity_percent}% · ${STATUS_LABEL[report.status]}`}
      actions={
        <div className="flex flex-wrap gap-2">
          <Link to={`/contests/${contestId}/fairplay`}>
            <Button variant="secondary">К списку</Button>
          </Link>
          {report.status !== "reviewed" && (
            <Button loading={busy} onClick={review}>
              Отметить проверенным
            </Button>
          )}
        </div>
      }
    >
      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {notice && <p className="mb-4 text-sm text-emerald-300">{notice}</p>}
      <p className="mb-4 text-sm text-zinc-300">{report.explanation}</p>
      <p className="mb-6 text-xs text-zinc-500">
        {report.username}: {formatDate(report.submitted_at)} · {report.matched_username}: {formatDate(report.matched_submitted_at)}
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <h2 className="mb-2 text-sm text-zinc-400">{report.username}</h2>
          <CodeView code={report.source_code} fragments={report.fragments} />
        </div>
        <div>
          <h2 className="mb-2 text-sm text-zinc-400">{report.matched_username}</h2>
          <CodeView code={report.matched_source_code} fragments={report.matched_fragments} />
        </div>
      </div>
    </Page>
  );
}
