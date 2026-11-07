import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { PhaseBadge } from "../components/badges";
import { Alert, Button, EmptyState, LoadingBlock, Page, cx } from "../components/ui";
import { formatDate, formatDuration, formatLabel } from "../lib/format";
import type { Contest, Phase } from "../types";

const TABS: Array<{ id: "all" | Phase; label: string }> = [
  { id: "all", label: "Все" },
  { id: "running", label: "Идут" },
  { id: "upcoming", label: "Скоро" },
  { id: "finished", label: "Завершены" },
  { id: "draft", label: "Черновики" },
];

export function ContestsPage() {
  const { user } = useAuth();
  const [contests, setContests] = useState<Contest[]>([]);
  const [phase, setPhase] = useState<(typeof TABS)[number]["id"]>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Contest[]>("/contests")
      .then(setContests)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Не удалось загрузить соревнования"))
      .finally(() => setLoading(false));
  }, [user]);

  const visibleTabs = user?.can_organize ? TABS : TABS.filter((tab) => tab.id !== "draft");
  const filtered = contests.filter((contest) => phase === "all" || contest.phase === phase);

  return (
    <Page
      title="Соревнования"
      subtitle="Зарегистрируйтесь, решайте задачи турнира и смотрите таблицу."
      actions={
        user?.can_organize ? (
          <Link to="/contests/new">
            <Button>Создать соревнование</Button>
          </Link>
        ) : undefined
      }
    >
      <div className="mb-4 flex flex-wrap gap-2">
        {visibleTabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setPhase(tab.id)}
            className={cx("rounded-lg px-3 py-1.5 text-sm", phase === tab.id ? "bg-violet-600 text-white" : "bg-white/5 text-zinc-300 hover:bg-white/10")}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {loading ? (
        <LoadingBlock label="Загрузка соревнований..." />
      ) : filtered.length === 0 ? (
        <EmptyState title="Список пуст" text="В этой категории пока нет соревнований." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {filtered.map((contest) => (
            <Link key={contest.id} to={`/contests/${contest.id}`} className="card flex flex-col p-5 transition hover:border-violet-500/40">
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-lg font-medium">{contest.title}</h2>
                <PhaseBadge value={contest.phase} />
              </div>
              <p className="mt-2 line-clamp-3 flex-1 text-sm text-zinc-400">{contest.description}</p>
              <p className="mt-4 text-xs text-zinc-500">
                {formatLabel[contest.participation_format]} · {contest.problem_count} задач · {contest.participant_count} участников · {formatDuration(contest.duration_minutes)} · старт {formatDate(contest.start_time)}
              </p>
              <p className="mt-2 text-xs text-zinc-400">
                Организатор {contest.organizer_name}
                {contest.organization_name ? ` · ${contest.organization_name}` : ""}
                {contest.is_registered ? " · вы участвуете" : ""}
              </p>
            </Link>
          ))}
        </div>
      )}
    </Page>
  );
}
