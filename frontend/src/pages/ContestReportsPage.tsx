import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError, downloadApi } from "../api";
import { Alert, Button, EmptyState, LoadingBlock, Page } from "../components/ui";
import { formatDate } from "../lib/format";
import type { ContestReport } from "../types";

const FORMAT_LABEL = { pdf: "PDF", xlsx: "XLSX", csv: "CSV" };

export function ContestReportsPage() {
  const { contestId } = useParams();
  const [reports, setReports] = useState<ContestReport[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");

  function load() {
    setLoading(true);
    api<ContestReport[]>(`/contests/${contestId}/reports`)
      .then((rows) => {
        setReports(rows);
        setError("");
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Не удалось открыть отчёты"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, [contestId]);

  async function create(reportFormat: ContestReport["report_format"]) {
    setBusy(reportFormat);
    setError("");
    setNotice("");
    try {
      const created = await api<ContestReport>(`/contests/${contestId}/reports`, {
        method: "POST",
        body: JSON.stringify({ report_format: reportFormat }),
      });
      setReports((current) => [created, ...current]);
      setNotice(`Файл ${created.file_name} сформирован.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось сформировать отчёт");
    } finally {
      setBusy("");
    }
  }

  async function download(report: ContestReport) {
    setError("");
    try {
      await downloadApi(`/contests/${contestId}/reports/${report.id}/download`, report.file_name);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось скачать отчёт");
    }
  }

  if (loading) return <LoadingBlock label="Загрузка отчётов..." />;

  return (
    <Page
      title="Итоговый отчёт"
      subtitle="Файл фиксирует результаты завершённого турнира. Он не заменяет документ для присвоения спортивного разряда."
      actions={
        <Link to={`/contests/${contestId}`}>
          <Button variant="secondary">К турниру</Button>
        </Link>
      }
    >
      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {notice && <p className="mb-4 text-sm text-emerald-300">{notice}</p>}
      <div className="mb-6 flex flex-wrap gap-2">
        {(["pdf", "xlsx", "csv"] as const).map((reportFormat) => (
          <Button key={reportFormat} loading={busy === reportFormat} disabled={Boolean(busy)} onClick={() => create(reportFormat)}>
            Сформировать {FORMAT_LABEL[reportFormat]}
          </Button>
        ))}
      </div>
      {reports.length === 0 ? (
        <EmptyState title="Отчётов ещё нет" text="После завершения турнира здесь появятся PDF, XLSX и CSV." />
      ) : (
        <ul className="space-y-3">
          {reports.map((report) => (
            <li key={report.id} className="card flex flex-wrap items-center justify-between gap-3 p-4">
              <div>
                <p className="font-medium">
                  {FORMAT_LABEL[report.report_format]} · {report.file_name}
                </p>
                <p className="text-xs text-zinc-500">
                  {report.created_by} · {formatDate(report.created_at)}
                </p>
              </div>
              <Button variant="secondary" onClick={() => download(report)}>
                Скачать
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Page>
  );
}
