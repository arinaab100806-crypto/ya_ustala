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

export function ProblemsPage() {
  const [search, setSearch] = useState("");
  const [difficulty, setDifficulty] = useState<"" | Difficulty>("");
  const [category, setCategory] = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const [problems, setProblems] = useState<Problem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api<string[]>("/problems/categories")
      .then(setCategories)
      .catch(() => setCategories([]));
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (difficulty) params.set("difficulty", difficulty);
      if (category) params.set("category", category);
      setLoading(true);
      api<Problem[]>(`/problems?${params.toString()}`)
        .then((rows) => {
          setProblems(rows);
          setError("");
        })
        .catch((err) => setError(err instanceof ApiError ? err.message : "Не удалось загрузить задачи"))
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(timer);
  }, [search, difficulty, category]);

  return (
    <Page title="Задачи" subtitle="Выберите задачу, откройте условие и отправьте решение.">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <input
          className="input sm:max-w-sm"
          placeholder="Поиск по названию"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((filter) => (
            <button
              key={filter.id || "all"}
              onClick={() => setDifficulty(filter.id)}
              className={cx(
                "rounded-lg px-3 py-1.5 text-sm transition",
                difficulty === filter.id ? "bg-violet-600 text-white" : "bg-white/5 text-zinc-300 hover:bg-white/10",
              )}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        <button
          onClick={() => setCategory("")}
          className={cx("rounded-lg px-3 py-1.5 text-sm transition", category === "" ? "bg-white/15 text-white" : "bg-white/5 text-zinc-300 hover:bg-white/10")}
        >
          Все категории
        </button>
        {categories.map((item) => (
          <button
            key={item}
            onClick={() => setCategory(item)}
            className={cx("rounded-lg px-3 py-1.5 text-sm transition", category === item ? "bg-white/15 text-white" : "bg-white/5 text-zinc-300 hover:bg-white/10")}
          >
            {item}
          </button>
        ))}
      </div>
      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {loading ? (
        <LoadingBlock label="Загрузка задач..." />
      ) : problems.length === 0 ? (
        <EmptyState title="Ничего не найдено" text="Измените запрос или сбросьте фильтры." />
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-white/10 text-xs uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Задача</th>
                  <th className="px-4 py-3 text-right font-medium">Решений</th>
                </tr>
              </thead>
              <tbody>
                {problems.map((problem) => (
                  <tr key={problem.id} className="border-b border-white/5 last:border-0 hover:bg-white/[0.03]">
                    <td className="px-4 py-3">
                      <Link to={`/problems/${problem.id}`} className="group flex items-start gap-3">
                        <span className={cx("mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full", problem.solved_by_me ? "bg-emerald-400" : "bg-zinc-700")} />
                        <span className="min-w-0">
                          <span className="flex flex-wrap items-center gap-2">
                            <span className="font-medium text-white group-hover:text-violet-200">{problem.title}</span>
                            <DifficultyBadge value={problem.difficulty} />
                          </span>
                          <span className="mt-1 block text-zinc-400">{problem.short_description}</span>
                          <span className="mt-1 block text-xs text-zinc-500">
                            {problem.category} · {problem.author_name}
                          </span>
                        </span>
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-right text-zinc-300">{problem.accepted_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <div className="mt-4">
        <Link to="/contests">
          <Button variant="ghost">Смотреть соревнования</Button>
        </Link>
      </div>
    </Page>
  );
}
