from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

import httpx

from . import config
from .models import TestCase
from .services import clip, normalize_output


class JudgeServiceError(Exception):
    pass


class JudgeUnavailable(JudgeServiceError):
    pass


@dataclass
class JudgeOutcome:
    verdict: str
    message: str
    runtime_ms: Optional[int]
    tests_passed: int
    tests_total: int
    judge_mode: str
    failed_input: Optional[str] = None
    failed_expected: Optional[str] = None
    failed_actual: Optional[str] = None


def judge_code(
    source: str,
    language: str,
    tests: Sequence[TestCase],
    time_limit_ms: int,
    memory_limit_mb: int,
    samples_only: bool,
) -> JudgeOutcome:
    selected = [test for test in tests if test.is_sample] if samples_only else list(tests)
    if samples_only and not selected:
        selected = list(tests[:1])
    if not selected:
        raise JudgeServiceError("У задачи нет тестов")
    if config.judge_mode() != "judge0":
        raise JudgeUnavailable("Проверка кода недоступна: не задан JUDGE0_URL. Вердикт не выставлен.")
    outcome = _judge_judge0(source, language, selected, time_limit_ms, memory_limit_mb)
    outcome.tests_total = len(selected)
    if samples_only and outcome.verdict == "OK":
        outcome.message = "Примеры пройдены."
    return outcome


def _fail(
    verdict: str,
    message: str,
    passed: int,
    total: int,
    runtime_ms: Optional[int],
    test: Optional[TestCase] = None,
    actual: Optional[str] = None,
) -> JudgeOutcome:
    reveal = test is not None and bool(test.is_sample)
    return JudgeOutcome(
        verdict=verdict,
        message=message,
        runtime_ms=runtime_ms,
        tests_passed=passed,
        tests_total=total,
        judge_mode=config.judge_mode(),
        failed_input=clip(test.input_data) if reveal else None,
        failed_expected=clip(test.expected_output) if reveal else None,
        failed_actual=clip(actual) if reveal and actual is not None else None,
    )


def _run_process(command: list[str], cwd: Path, stdin_data: str, timeout_sec: float) -> tuple[Optional[int], str, str, bool]:
    try:
        completed = subprocess.run(
            command,
            input=stdin_data.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(cwd),
            timeout=timeout_sec,
            env=_child_env(),
            check=False,
        )
        return (
            completed.returncode,
            completed.stdout.decode("utf-8", errors="replace"),
            completed.stderr.decode("utf-8", errors="replace"),
            False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return None, stdout, stderr, True


def _child_env() -> dict[str, str]:
    import os

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def _missing_runtime(language: str) -> str:
    names = {
        "python": "Python",
        "cpp": "g++",
        "java": "Java (javac и java)",
        "javascript": "Node.js",
    }
    tool = names.get(language, language)
    return (
        f"Не найден компилятор или интерпретатор для {tool}. "
        "Добавьте его в PATH или настройте Judge0."
    )


def _judge_demo(source: str, language: str, tests: Sequence[TestCase], time_limit_ms: int) -> JudgeOutcome:
    total = len(tests)
    tmp = Path(tempfile.mkdtemp(prefix="codearena-"))
    try:
        compile_cmd, run_cmd = _prepare_demo(language, source, tmp)
        if compile_cmd == "missing":
            return _fail("CE", _missing_runtime(language), 0, total, None)
        if compile_cmd:
            code, _stdout, stderr, timed_out = _run_process(compile_cmd, tmp, "", 20)
            if timed_out or code != 0:
                details = clip(stderr, 4000) or "Ошибка компиляции"
                return _fail("CE", details, 0, total, None)
        runtime_total = 0
        timeout_sec = time_limit_ms / 1000 + 1.5
        for index, test in enumerate(tests, start=1):
            started = time.perf_counter()
            code, stdout, stderr, timed_out = _run_process(run_cmd, tmp, test.input_data, timeout_sec)
            runtime_total += int((time.perf_counter() - started) * 1000)
            if timed_out:
                return _fail("TLE", f"Превышено время на тесте {index}.", index - 1, total, runtime_total, test)
            if code not in (0, None):
                verdict = "CE" if _looks_like_compile_error(language, stderr) else "RE"
                title = "Ошибка компиляции" if verdict == "CE" else f"Ошибка выполнения на тесте {index}."
                details = clip(stderr, 4000) or title
                message = details if verdict == "CE" else f"{title}\n{details}"
                return _fail(verdict, message, index - 1, total, runtime_total, test, stdout)
            if len(stdout) > 100_000:
                return _fail("RE", f"Слишком большой вывод на тесте {index}.", index - 1, total, runtime_total, test)
            if normalize_output(stdout) != normalize_output(test.expected_output):
                return _fail(
                    "WA",
                    f"Неверный ответ на тесте {index}.",
                    index - 1,
                    total,
                    runtime_total,
                    test,
                    stdout,
                )
        return JudgeOutcome(
            verdict="OK",
            message="Все тесты пройдены.",
            runtime_ms=runtime_total,
            tests_passed=total,
            tests_total=total,
            judge_mode="demo",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _looks_like_compile_error(language: str, stderr: str) -> bool:
    if language == "python":
        return "SyntaxError" in stderr or "IndentationError" in stderr
    if language == "javascript":
        return "SyntaxError" in stderr
    return False


def _prepare_demo(language: str, source: str, tmp: Path):
    if language == "python":
        path = tmp / "main.py"
        path.write_text(source, encoding="utf-8")
        return None, [sys.executable, str(path)]
    if language == "javascript":
        node = shutil.which("node")
        if not node:
            return "missing", []
        path = tmp / "main.js"
        path.write_text(source, encoding="utf-8")
        return None, [node, str(path)]
    if language == "cpp":
        compiler = shutil.which("g++")
        if not compiler:
            return "missing", []
        source_path = tmp / "main.cpp"
        exe_path = tmp / "main.exe"
        source_path.write_text(source, encoding="utf-8")
        return [compiler, "-O2", "-std=c++17", str(source_path), "-o", str(exe_path)], [str(exe_path)]
    if language == "java":
        javac = shutil.which("javac")
        java = shutil.which("java")
        if not javac or not java:
            return "missing", []
        source_path = tmp / "Main.java"
        source_path.write_text(source, encoding="utf-8")
        return [javac, str(source_path)], [java, "-cp", str(tmp), "Main"]
    raise JudgeServiceError("Неподдерживаемый язык")


def _judge_judge0(
    source: str,
    language: str,
    tests: Sequence[TestCase],
    time_limit_ms: int,
    memory_limit_mb: int,
) -> JudgeOutcome:
    total = len(tests)
    runtime_total = 0
    try:
        with httpx.Client(timeout=60) as client:
            for index, test in enumerate(tests, start=1):
                data = _judge0_submission(client, source, language, test.input_data, time_limit_ms, memory_limit_mb)
                status_id = (data.get("status") or {}).get("id")
                runtime_total += _parse_time_ms(data) or 0
                stdout = data.get("stdout") or ""
                stderr = data.get("stderr") or ""
                compile_output = data.get("compile_output") or ""
                if status_id == 6:
                    return _fail("CE", clip(compile_output or stderr, 4000) or "Ошибка компиляции", index - 1, total, runtime_total)
                if status_id == 5:
                    return _fail("TLE", f"Превышено время на тесте {index}.", index - 1, total, runtime_total, test)
                if status_id in (7, 8, 9, 10, 11, 12, 13, 14) or status_id not in (3, 4):
                    details = clip(stderr or data.get("message") or "Ошибка выполнения", 4000)
                    return _fail("RE", f"Ошибка выполнения на тесте {index}.\n{details}", index - 1, total, runtime_total, test, stdout)
                if normalize_output(stdout) != normalize_output(test.expected_output):
                    return _fail("WA", f"Неверный ответ на тесте {index}.", index - 1, total, runtime_total, test, stdout)
    except httpx.HTTPError as exc:
        raise JudgeServiceError("Не удалось связаться с Judge0. Проверьте JUDGE0_URL и ключ API.") from exc
    return JudgeOutcome(
        verdict="OK",
        message="Все тесты пройдены.",
        runtime_ms=runtime_total,
        tests_passed=total,
        tests_total=total,
        judge_mode="judge0",
    )


def _judge0_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if config.JUDGE0_API_KEY:
        headers["X-RapidAPI-Key"] = config.JUDGE0_API_KEY
        headers["X-RapidAPI-Host"] = config.JUDGE0_API_HOST or "judge0-ce.p.rapidapi.com"
    return headers


def _judge0_submission(
    client: httpx.Client,
    source: str,
    language: str,
    stdin_data: str,
    time_limit_ms: int,
    memory_limit_mb: int,
) -> dict:
    payload = {
        "source_code": source,
        "language_id": config.LANGUAGE_IDS[language],
        "stdin": stdin_data,
        "cpu_time_limit": min(10, max(0.5, time_limit_ms / 1000)),
        "memory_limit": memory_limit_mb * 1024,
    }
    response = client.post(
        f"{config.JUDGE0_URL}/submissions",
        params={"base64_encoded": "false", "wait": "true"},
        json=payload,
        headers=_judge0_headers(),
    )
    if response.status_code >= 400:
        raise JudgeServiceError(f"Judge0 ответил с ошибкой {response.status_code}")
    data = response.json()
    token = data.get("token")
    polls = 0
    while (data.get("status") or {}).get("id") in (1, 2) and token and polls < 25:
        polls += 1
        time.sleep(0.4)
        poll = client.get(
            f"{config.JUDGE0_URL}/submissions/{token}",
            params={"base64_encoded": "false"},
            headers=_judge0_headers(),
        )
        if poll.status_code >= 400:
            raise JudgeServiceError("Не удалось получить результат Judge0")
        data = poll.json()
    if not data.get("status"):
        raise JudgeServiceError("Judge0 вернул ответ без статуса")
    return data


def _parse_time_ms(data: dict) -> Optional[int]:
    raw = data.get("time")
    if raw in (None, ""):
        return None
    try:
        return int(float(raw) * 1000)
    except (TypeError, ValueError):
        return None
