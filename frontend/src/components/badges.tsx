import { difficultyLabel, phaseLabel, verdictText } from "../lib/format";
import type { Difficulty, Phase, Verdict } from "../types";
import { cx } from "./ui";

export function DifficultyBadge({ value }: { value: Difficulty }) {
  const tone = {
    easy: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/25",
    medium: "bg-amber-500/10 text-amber-200 ring-amber-500/25",
    hard: "bg-rose-500/10 text-rose-300 ring-rose-500/25",
  }[value];
  return <span className={cx("inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset", tone)}>{difficultyLabel[value]}</span>;
}

export function PhaseBadge({ value }: { value: Phase }) {
  const tone = {
    draft: "bg-zinc-500/10 text-zinc-300 ring-zinc-500/30",
    upcoming: "bg-violet-500/10 text-violet-200 ring-violet-500/30",
    running: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30",
    finished: "bg-zinc-500/10 text-zinc-400 ring-zinc-600/40",
  }[value];
  return <span className={cx("inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset", tone)}>{phaseLabel[value]}</span>;
}

export function VerdictBadge({ value }: { value: Verdict | string }) {
  const tone =
    {
      OK: "bg-emerald-500/15 text-emerald-300",
      WA: "bg-red-500/15 text-red-300",
      TLE: "bg-amber-500/15 text-amber-200",
      RE: "bg-orange-500/15 text-orange-200",
      CE: "bg-fuchsia-500/15 text-fuchsia-200",
    }[value] ?? "bg-zinc-500/15 text-zinc-300";
  return <span className={cx("inline-flex min-w-12 justify-center rounded-md px-2 py-0.5 font-mono text-xs font-semibold", tone)}>{value}</span>;
}

export function VerdictCaption({ value }: { value: Verdict }) {
  return <span className="text-sm text-zinc-300">{verdictText[value]}</span>;
}
