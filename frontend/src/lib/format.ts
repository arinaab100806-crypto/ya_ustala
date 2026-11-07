import type { Difficulty, Language, ParticipationFormat, Phase, Role, Verdict } from "../types";

export const difficultyLabel: Record<Difficulty, string> = {
  easy: "Легкий",
  medium: "Средний",
  hard: "Сложный",
};

export const phaseLabel: Record<Phase, string> = {
  draft: "Черновик",
  upcoming: "Скоро",
  running: "Идёт",
  finished: "Завершено",
};

export const formatLabel: Record<ParticipationFormat, string> = {
  individual: "Индивидуальный",
  team: "Командный",
};

export const verdictText: Record<Verdict, string> = {
  OK: "Правильный ответ",
  WA: "Неправильный ответ",
  TLE: "Превышено время",
  RE: "Ошибка выполнения",
  CE: "Ошибка компиляции",
};

export const languageLabel: Record<Language, string> = {
  python: "Python",
  cpp: "C++",
  java: "Java",
  javascript: "JavaScript",
};

export const roleLabel: Record<Role, string> = {
  participant: "Участник",
  organizer: "Организатор",
  admin: "Администратор",
};

export function formatDate(iso: string) {
  return new Date(iso).toLocaleString("ru-RU", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDuration(minutes: number) {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours && rest) return `${hours} ч ${rest} мин`;
  if (hours) return `${hours} ч`;
  return `${rest} мин`;
}

export function formatPenalty(seconds: number) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

export function toLocalInput(iso: string) {
  const date = new Date(iso);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
