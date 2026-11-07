import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import { DifficultyBadge } from "../components/badges";
import { Alert, Button, EmptyState, LoadingBlock, Page, cx } from "../components/ui";
import { difficultyLabel } from "../lib/format";
import type { Difficulty, Problem } from "../types";

const FILTERS: Array<{ id: "" | Difficulty; label: string }> = [
  { id: "", label: "Все" },
  { id: "easy", label: difficultyLabel.easy },
  { id: "medium", label: difficultyLabel.medium },
  { id: "hard", label: difficultyLabel.hard },
];

export function ProductionPage() {
  const [all, setAll] = useState<Problem[]>([]);
  const [search, setSearch] = useState("");
  const [difficulty, setDifficulty] = useState<"" | Difficulty>("");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Problem[]>("/problems/production")
      .then((rows) => {
        setAll(rows);
        setError("");
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Не удалось загрузить витрину"))
      .finally(() => setLoading(false));
  }, []);

  const categories = [...new Set(all.map((problem) => problem.category))];
  const needle = search.trim().toLowerCase();
  const problems = all.filter((problem) => {
    if (difficulty && problem.difficulty !== difficulty) return false;
    if (category && problem.category !== category) return false;
    if (needle && !problem.title.toLowerCase().includes(needle) && !problem.short_description.toLowerCase().includes(needle)) return false;
    return true;
  });

  return (
    <Page title="Производственные задачи" subtitle="Задачи организаций по реальным процессам. Скрытые задачи сюда не попадают.">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <input className="input sm:max-w-sm" placeholder="Поиск по названию" value={search} onChange={(event) => setSearch(event.target.value)} />
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((filter) => (
            <button
              key={filter.id || "all"}
              onClick={() => setDifficulty(filter.id)}
              className={cx("rounded-lg px-3 py-1.5 text-sm", difficulty === filter.id ? "bg-violet-600 text-white" : "bg-white/5 text-zinc-300 hover:bg-white/10")}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </div>
      {categories.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-2">
          <button onClick={() => setCategory("")} className={cx("rounded-lg px-3 py-1.5 text-sm", category === "" ? "bg-white/15 text-white" : "bg-white/5 text-zinc-300")}>
            Все категории
          </button>
          {categories.map((item) => (
            <button key={item} onClick={() => setCategory(item)} className={cx("rounded-lg px-3 py-1.5 text-sm", category === item ? "bg-white/15 text-white" : "bg-white/5 text-zinc-300")}>
              {item}
            </button>
          ))}
        </div>
      )}
      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {loading ? (
        <LoadingBlock label="Загрузка витрины..." />
      ) : problems.length === 0 ? (
        <EmptyState title="Пока нет опубликованных задач" text="Организация публикует производственную задачу из своего кабинета." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {problems.map((problem) => (
            <Link key={problem.id} to={`/problems/${problem.id}`} className="card block p-5 transition hover:border-violet-500/40">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="font-medium text-white">{problem.title}</h2>
                <DifficultyBadge value={problem.difficulty} />
              </div>
              <p className="mt-2 text-sm text-zinc-400">{problem.short_description}</p>
              <p className="mt-3 text-xs text-zinc-500">
                {problem.author_name} · {problem.category} · опубликована · {problem.accepted_count} решений
              </p>
            </Link>
          ))}
        </div>
      )}
      <div className="mt-4">
        <Link to="/problems">
          <Button variant="ghost">Алгоритмические задачи</Button>
        </Link>
      </div>
    </Page>
  );
}
