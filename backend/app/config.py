from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_dotenv() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "codearena-dev-secret-key-change-me")
DB_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "codearena.db")))
JUDGE0_URL = os.getenv("JUDGE0_URL", "").strip().rstrip("/")
JUDGE0_API_KEY = os.getenv("JUDGE0_API_KEY", "").strip()
JUDGE0_API_HOST = os.getenv("JUDGE0_API_HOST", "").strip()

LANGUAGE_IDS = {
    "python": int(os.getenv("JUDGE0_LANG_PYTHON", "71")),
    "cpp": int(os.getenv("JUDGE0_LANG_CPP", "54")),
    "java": int(os.getenv("JUDGE0_LANG_JAVA", "62")),
    "javascript": int(os.getenv("JUDGE0_LANG_JAVASCRIPT", "63")),
}

LANGUAGES = ("python", "cpp", "java", "javascript")


def judge_mode() -> str:
    return "judge0" if JUDGE0_URL else "unavailable"


def judge_label() -> str:
    if judge_mode() == "judge0":
        return "Judge0"
    return "Проверка недоступна"
