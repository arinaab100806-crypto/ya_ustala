import axios from "axios";

const FIELD_NAMES: Record<string, string> = {
  username: "имя пользователя",
  email: "email",
  password: "пароль",
  role: "роль",
  title: "название",
  description: "описание",
  start_time: "дата начала",
  duration_minutes: "продолжительность",
  problem_ids: "список задач",
  source_code: "код",
  language: "язык",
  organization_name: "название организации",
};

const client = axios.create({ baseURL: "/api" });

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function messageFromBody(data: unknown): string {
  if (!data || typeof data !== "object" || !("detail" in data)) {
    return "Ошибка запроса";
  }
  const detail = (data as { detail: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { loc?: unknown[]; msg?: string };
    const field = Array.isArray(first.loc) ? first.loc.filter((part) => part !== "body").join(".") : "";
    const label = FIELD_NAMES[field] ?? field;
    if (label) return `Проверьте поле «${label}»`;
    return "Проверьте заполнение формы";
  }
  return "Ошибка запроса";
}

export async function api<T>(path: string, options: { method?: string; body?: string } = {}): Promise<T> {
  const token = localStorage.getItem("token");
  try {
    const response = await client.request<T>({
      url: path,
      method: options.method ?? "GET",
      data: options.body,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (!error.response) {
        throw new ApiError(0, "Сервер недоступен. Запустите backend на порту 8000.");
      }
      throw new ApiError(error.response.status, messageFromBody(error.response.data));
    }
    throw new ApiError(0, "Сервер недоступен. Запустите backend на порту 8000.");
  }
}

export async function downloadApi(path: string, filename: string): Promise<void> {
  const token = localStorage.getItem("token");
  try {
    const response = await client.request<Blob>({
      url: path,
      responseType: "blob",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    const url = URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    if (axios.isAxiosError(error) && error.response) {
      throw new ApiError(error.response.status, "Не удалось скачать отчёт");
    }
    throw new ApiError(0, "Сервер недоступен. Запустите backend на порту 8000.");
  }
}
