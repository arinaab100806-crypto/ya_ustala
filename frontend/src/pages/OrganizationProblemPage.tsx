import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { Alert, Button, LoadingBlock, Page, TextArea, TextField } from "../components/ui";
import { difficultyLabel, languageLabel } from "../lib/format";
import type { Difficulty, OrgProblemDetail, ProblemResult } from "../types";

const EMPTY: OrgProblemDetail = {
  id: 0,
  title: "",
  short_description: "",
  statement: "",
  input_format: "",
  output_format: "",
  constraints: "",
  difficulty: "easy",
  category: "общее",
  kind: "algorithmic",
  publication_status: "hidden",
  accepted_count: 0,
  time_limit_ms: 2000,
  memory_limit_mb: 256,
  tests: [],
};

export function OrganizationProblemPage() {
  const { orgId, problemId } = useParams();
  const navigate = useNavigate();
  const editing = Boolean(problemId);
  const [form, setForm] = useState<OrgProblemDetail>(EMPTY);
  const [sampleInput, setSampleInput] = useState("");
  const [sampleOutput, setSampleOutput] = useState("");
  const [hiddenInput, setHiddenInput] = useState("");
  const [hiddenOutput, setHiddenOutput] = useState("");
  const [results, setResults] = useState<ProblemResult[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(editing);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!problemId) return;
    api<OrgProblemDetail>(`/organizations/${orgId}/problems/${problemId}`)
      .then((problem) => {
        setForm(problem);
        const sample = problem.tests.find((test) => test.is_sample);
        const hidden = problem.tests.find((test) => !test.is_sample);
        setSampleInput(sample?.input_data ?? "");
        setSampleOutput(sample?.expected_output ?? "");
        setHiddenInput(hidden?.input_data ?? "");
        setHiddenOutput(hidden?.expected_output ?? "");
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Не удалось открыть задачу"))
      .finally(() => setLoading(false));
    api<ProblemResult[]>(`/organizations/${orgId}/problems/${problemId}/results`)
      .then(setResults)
      .catch(() => setResults([]));
  }, [orgId, problemId]);

  function payload() {
    const tests = [{ input_data: sampleInput, expected_output: sampleOutput, is_sample: true }];
    if (hiddenInput.trim() || hiddenOutput.trim()) {
      tests.push({ input_data: hiddenInput, expected_output: hiddenOutput, is_sample: false });
    }
    return {
      title: form.title,
      short_description: form.short_description,
      statement: form.statement,
      input_format: form.input_format,
      output_format: form.output_format,
      constraints: form.constraints,
      difficulty: form.difficulty,
      category: form.category,
      kind: form.kind,
      time_limit_ms: form.time_limit_ms,
      memory_limit_mb: form.memory_limit_mb,
      tests,
    };
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const path = editing ? `/organizations/${orgId}/problems/${problemId}` : `/organizations/${orgId}/problems`;
      const saved = await api<OrgProblemDetail>(path, { method: editing ? "PUT" : "POST", body: JSON.stringify(payload()) });
      navigate(`/organization/${orgId}/problems/${saved.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось сохранить задачу");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <LoadingBlock />;

  return (
    <Page
      title={editing ? "Задача организации" : "Новая задача"}
      subtitle="Новая задача сохраняется скрытой. Опубликовать её можно в кабинете."
      actions={
        <Link to={`/organization/${orgId}`}>
          <Button variant="secondary">К кабинету</Button>
        </Link>
      }
    >
      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      <form onSubmit={save} className="grid gap-4 lg:grid-cols-2">
        <div className="card space-y-4 p-5">
          <label className="block text-sm text-zinc-300">
            Тип
            <select className="input mt-1.5" value={form.kind} onChange={(event) => setForm({ ...form, kind: event.target.value as OrgProblemDetail["kind"] })}>
              <option value="algorithmic">Алгоритмическая</option>
              <option value="production">Производственная</option>
            </select>
          </label>
          <TextField label="Название" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} required minLength={3} />
          <TextField label="Кратко" value={form.short_description} onChange={(event) => setForm({ ...form, short_description: event.target.value })} required />
          <TextArea label="Условие" value={form.statement} onChange={(event) => setForm({ ...form, statement: event.target.value })} required rows={6} />
          <TextField label="Входные данные" value={form.input_format} onChange={(event) => setForm({ ...form, input_format: event.target.value })} required />
          <TextField label="Выходные данные" value={form.output_format} onChange={(event) => setForm({ ...form, output_format: event.target.value })} required />
          <TextField label="Ограничения" value={form.constraints} onChange={(event) => setForm({ ...form, constraints: event.target.value })} required />
        </div>
        <div className="card space-y-4 p-5">
          <label className="block text-sm text-zinc-300">
            Сложность
            <select className="input mt-1.5" value={form.difficulty} onChange={(event) => setForm({ ...form, difficulty: event.target.value as Difficulty })}>
              {(Object.keys(difficultyLabel) as Difficulty[]).map((item) => (
                <option key={item} value={item}>
                  {difficultyLabel[item]}
                </option>
              ))}
            </select>
          </label>
          <TextField label="Категория" value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} required />
          <TextField label="Лимит времени, мс" type="number" min={200} max={10000} value={form.time_limit_ms} onChange={(event) => setForm({ ...form, time_limit_ms: Number(event.target.value) })} required />
          <TextArea label="Пример, вход" value={sampleInput} onChange={(event) => setSampleInput(event.target.value)} required rows={3} />
          <TextArea label="Пример, выход" value={sampleOutput} onChange={(event) => setSampleOutput(event.target.value)} required rows={3} />
          <TextArea label="Скрытый тест, вход" value={hiddenInput} onChange={(event) => setHiddenInput(event.target.value)} rows={3} />
          <TextArea label="Скрытый тест, выход" value={hiddenOutput} onChange={(event) => setHiddenOutput(event.target.value)} rows={3} />
          <Button type="submit" loading={busy}>
            Сохранить
          </Button>
        </div>
      </form>
      {editing && (
        <section className="mt-8">
          <h2 className="mb-3 font-medium">Результаты решений</h2>
          {results.length === 0 ? (
            <p className="text-sm text-zinc-400">Отправок пока нет. Исходный код решений здесь не показывается.</p>
          ) : (
            <div className="card overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-zinc-500">
                  <tr>
                    <th className="px-4 py-3">Участник</th>
                    <th className="px-4 py-3">Вердикт</th>
                    <th className="px-4 py-3">Язык</th>
                    <th className="px-4 py-3">Тесты</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((result) => (
                    <tr key={result.id} className="border-t border-white/5">
                      <td className="px-4 py-3">{result.username}</td>
                      <td className="px-4 py-3">{result.verdict}</td>
                      <td className="px-4 py-3">{languageLabel[result.language]}</td>
                      <td className="px-4 py-3">
                        {result.tests_passed}/{result.tests_total}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </Page>
  );
}
