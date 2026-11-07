"""Проверка основных сценариев API. Запуск: py -3 smoke_test.py из папки backend."""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(tempfile.gettempdir()) / "codearena-smoke.db"
if DB_PATH.exists():
    DB_PATH.unlink()
os.environ["DATABASE_PATH"] = str(DB_PATH)
os.environ["JUDGE0_URL"] = ""
os.environ["ADMIN_EMAIL"] = ""
os.environ["ADMIN_PASSWORD"] = ""
os.environ["ADMIN_USERNAME"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Submission, User  # noqa: E402

SOLUTIONS = {
    "Сумма двух чисел": "a, b = map(int, input().split())\nprint(a + b)\n",
    "Максимум из трёх чисел": "print(max(map(int, input().split())))\n",
    "Сумма последовательности": "n = int(input())\nprint(sum(map(int, input().split())))\n",
    "Палиндром": "s = input().strip()\nprint('YES' if s == s[::-1] else 'NO')\n",
    "Факториал": "n = int(input())\nr = 1\nfor i in range(2, n + 1):\n    r *= i\nprint(r)\n",
    "Простое число": (
        "n = int(input())\n"
        "if n < 2:\n"
        "    print('NO')\n"
        "else:\n"
        "    ok = True\n"
        "    i = 2\n"
        "    while i * i <= n:\n"
        "        if n % i == 0:\n"
        "            ok = False\n"
        "            break\n"
        "        i += 1\n"
        "    print('YES' if ok else 'NO')\n"
    ),
    "Число Фибоначчи": "n = int(input())\na, b = 0, 1\nfor _ in range(n):\n    a, b = b, a + b\nprint(a)\n",
    "Максимальная сумма отрезка": (
        "n = int(input())\n"
        "arr = list(map(int, input().split()))\n"
        "best = cur = arr[0]\n"
        "for x in arr[1:]:\n"
        "    cur = max(x, cur + x)\n"
        "    best = max(best, cur)\n"
        "print(best)\n"
    ),
    "Кратчайший путь в графе": (
        "from collections import deque\n"
        "n, m = map(int, input().split())\n"
        "g = [[] for _ in range(n + 1)]\n"
        "for _ in range(m):\n"
        "    u, v = map(int, input().split())\n"
        "    g[u].append(v)\n"
        "    g[v].append(u)\n"
        "s, t = map(int, input().split())\n"
        "dist = [-1] * (n + 1)\n"
        "dist[s] = 0\n"
        "q = deque([s])\n"
        "while q:\n"
        "    u = q.popleft()\n"
        "    for v in g[u]:\n"
        "        if dist[v] == -1:\n"
        "            dist[v] = dist[u] + 1\n"
        "            q.append(v)\n"
        "print(dist[t])\n"
    ),
}


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")
    print(f"OK: {message}")


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def main() -> None:
    with TestClient(app) as client:
        health = client.get("/api/health")
        expect(health.status_code == 200 and health.json()["ok"] is True, "health")
        system = client.get("/api/system").json()
        expect(system["judge_mode"] == "unavailable", "без Judge0 проверка недоступна")
        expect("недоступна" in system["judge_label"], "подпись недоступной проверки")

        short = client.post(
            "/api/auth/register",
            json={"username": "ab", "email": "ab@example.com", "password": "123456", "role": "participant"},
        )
        expect(short.status_code == 422, "короткое имя отклоняется")

        participant = client.post(
            "/api/auth/register",
            json={
                "username": "alice",
                "email": "alice@example.com",
                "password": "secret123",
                "role": "participant",
            },
        )
        expect(participant.status_code == 200, "регистрация участника")
        participant_token = participant.json()["access_token"]
        expect(participant.json()["user"]["role"] == "participant", "роль участника")

        duplicate = client.post(
            "/api/auth/register",
            json={
                "username": "Alice",
                "email": "other@example.com",
                "password": "secret123",
                "role": "participant",
            },
        )
        expect(duplicate.status_code == 400, "имя без учёта регистра занято")

        organizer = client.post(
            "/api/auth/register",
            json={
                "username": "bob",
                "email": "bob@example.com",
                "password": "secret123",
                "role": "organizer",
            },
        )
        expect(organizer.status_code == 200, "регистрация не даёт выбрать роль организатора")
        expect(organizer.json()["user"]["role"] == "participant", "обычная регистрация создаёт участника")
        expect(organizer.json()["user"]["can_organize"] is False, "участник не может создавать турниры")

        organizer = client.post(
            "/api/auth/register-organization",
            json={
                "username": "orgbob",
                "email": "orgbob@example.com",
                "password": "secret123",
                "organization_name": "Acme",
                "organization_description": "Корпоративный контур",
            },
        )
        expect(organizer.status_code == 200, "регистрация организации")
        org_user = organizer.json()["user"]
        expect(org_user["role"] == "participant" and org_user["can_organize"] is True, "владелец организации может организовывать")
        expect(org_user["organizations"][0]["member_role"] == "owner", "создатель становится владельцем")
        organizer_token = organizer.json()["access_token"]
        duplicate_org = client.post(
            "/api/auth/register-organization",
            json={
                "username": "orgbob2",
                "email": "orgbob2@example.com",
                "password": "secret123",
                "organization_name": "acme",
                "organization_description": "Повтор",
            },
        )
        expect(duplicate_org.status_code == 400, "название организации уникально")
        org_id = org_user["organizations"][0]["organization_id"]
        corporate_problem = {
            "title": "Корпоративная сумма",
            "short_description": "Сложите два числа для организации.",
            "statement": "Выведите сумму двух целых чисел.",
            "input_format": "Два числа через пробел.",
            "output_format": "Одно число.",
            "constraints": "Небольшие целые числа.",
            "difficulty": "easy",
            "category": "математика",
            "kind": "algorithmic",
            "time_limit_ms": 1000,
            "memory_limit_mb": 256,
            "tests": [
                {"input_data": "1 2", "expected_output": "3", "is_sample": True},
                {"input_data": "4 5", "expected_output": "9", "is_sample": False},
            ],
        }
        created_problem = client.post(f"/api/organizations/{org_id}/problems", headers=auth(organizer_token), json=corporate_problem)
        expect(created_problem.status_code == 200 and created_problem.json()["publication_status"] == "hidden", "организация создаёт скрытую задачу")
        hidden_id = created_problem.json()["id"]
        public_titles = [item["title"] for item in client.get("/api/problems").json()]
        expect("Корпоративная сумма" not in public_titles, "скрытая задача не в каталоге")
        hidden_run = client.post(
            "/api/run",
            headers=auth(participant_token),
            json={"problem_id": hidden_id, "language": "python", "source_code": "print(1)\n"},
        )
        expect(hidden_run.status_code == 404, "участник не запускает скрытую задачу")
        staff_run = client.post(
            "/api/run",
            headers=auth(organizer_token),
            json={"problem_id": hidden_id, "language": "python", "source_code": "print(1)\n"},
        )
        expect(staff_run.status_code == 503, "сотрудник доходит до проверки скрытой задачи")
        expect(client.post(f"/api/organizations/{org_id}/problems/{hidden_id}/publish", headers=auth(organizer_token)).status_code == 200, "организация публикует задачу")
        published = client.get("/api/problems").json()
        expect(any(item["title"] == "Корпоративная сумма" and item["author_name"] == "Acme" for item in published), "опубликованная задача видна с автором-организацией")
        production = dict(corporate_problem)
        production["title"] = "Смена склада"
        production["kind"] = "production"
        production["category"] = "логистика"
        production["statement"] = "Распределите смену: выведите сумму двух чисел."
        created_production = client.post(f"/api/organizations/{org_id}/problems", headers=auth(organizer_token), json=production)
        production_id = created_production.json()["id"]
        client.post(f"/api/organizations/{org_id}/problems/{production_id}/publish", headers=auth(organizer_token))
        showcase = client.get("/api/problems/production").json()
        expect(len(showcase) == 1 and showcase[0]["author_name"] == "Acme", "витрина производственных задач")
        expect(all(item["title"] != "Смена склада" for item in client.get("/api/problems").json()), "производственная задача не в алгоритмическом каталоге")
        expect(client.post(f"/api/organizations/{org_id}/problems", headers=auth(participant_token), json=corporate_problem).status_code == 403, "участник не создаёт задачи организации")
        outsider = client.post("/api/auth/register", json={"username": "dave", "email": "dave@example.com", "password": "secret123"})
        added = client.post(f"/api/organizations/{org_id}/members", headers=auth(organizer_token), json={"username": "dave"})
        expect(added.status_code == 200 and any(row["username"] == "dave" for row in added.json()["members"]), "владелец добавляет организатора")
        dave_token = outsider.json()["access_token"]
        expect(client.get("/api/auth/me", headers=auth(dave_token)).json()["can_organize"] is True, "сотрудник организации может организовывать")
        expect(client.get(f"/api/organizations/{org_id}/problems/{production_id}/results", headers=auth(organizer_token)).json() == [], "у новой задачи нет результатов")
        profile = client.patch(
            f"/api/organizations/{org_id}",
            headers=auth(organizer_token),
            json={"name": "Acme", "description": "Обновлённое описание", "logo_url": "https://example.com/logo.png"},
        )
        expect(profile.status_code == 200 and profile.json()["logo_url"] == "https://example.com/logo.png", "организация обновляет профиль")
        expect(client.get("/api/admin/users", headers=auth(participant_token)).status_code == 403, "участник не видит админку")

        bad_login = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "wrongpass"})
        expect(bad_login.status_code == 401, "неверный пароль")
        login = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "secret123"})
        expect(login.status_code == 200, "вход")
        participant_token = login.json()["access_token"]
        me = client.get("/api/auth/me", headers=auth(participant_token))
        expect(me.status_code == 200 and me.json()["username"] == "alice", "текущий пользователь")
        expect(client.get("/api/auth/me").status_code == 401, "закрытый маршрут без токена")

        db = SessionLocal()
        try:
            stored = db.query(User).filter(User.email == "alice@example.com").one()
            expect(stored.password_hash != "secret123" and "$" in stored.password_hash, "пароль хранится как хеш")
        finally:
            db.close()

        problems = client.get("/api/problems").json()
        expect(len(problems) == 10, "в каталоге задачи платформы и опубликованная задача организации")
        found = client.get("/api/problems", params={"search": "фибоначчи"}).json()
        expect(len(found) == 1 and found[0]["title"] == "Число Фибоначчи", "поиск по-русски")
        expect(found[0]["category"] == "математика" and found[0]["author_name"] == "ВолгаКод", "у задачи есть категория и автор")
        hard = client.get("/api/problems", params={"difficulty": "hard"}).json()
        expect(len(hard) == 2, "фильтр сложной сложности")
        graphs = client.get("/api/problems", params={"category": "графы"}).json()
        expect(len(graphs) == 1 and graphs[0]["title"] == "Кратчайший путь в графе", "фильтр категории")
        categories = client.get("/api/problems/categories").json()
        expect("строки" in categories and "математика" in categories, "список категорий")

        first = client.get(f"/api/problems/{problems[0]['id']}").json()
        expect(first["statement"] and first["examples"], "у задачи есть условие и примеры")
        expect("1000000000" not in str(first), "скрытые тесты не отдаются клиенту")

        forbidden = client.post(
            "/api/contests",
            headers=auth(participant_token),
            json={
                "title": "Чужое соревнование",
                "description": "Не должно создаться",
                "start_time": datetime.now(timezone.utc).isoformat(),
                "duration_minutes": 60,
                "problem_ids": [problems[0]["id"]],
            },
        )
        expect(forbidden.status_code == 403, "участник не создаёт соревнования")

        run = client.post(
            "/api/run",
            headers=auth(participant_token),
            json={"problem_id": problems[0]["id"], "language": "python", "source_code": SOLUTIONS["Сумма двух чисел"]},
        )
        expect(run.status_code == 503 and "JUDGE0_URL" in run.json()["detail"], "без Judge0 запуск не выдаёт вердикт")
        sent = client.post(
            "/api/submissions",
            headers=auth(participant_token),
            json={"problem_id": problems[0]["id"], "language": "python", "source_code": SOLUTIONS["Сумма двух чисел"]},
        )
        expect(sent.status_code == 503, "без Judge0 отправка не создаёт вердикт")
        expect(client.get("/api/submissions", headers=auth(participant_token)).json() == [], "непроверенное решение не сохраняется")

        dashboard = client.get("/api/dashboard", headers=auth(participant_token)).json()
        expect(dashboard["solved_count"] == 0, "без проверки решённые задачи не появляются")
        expect(dashboard["recent_submissions"] == [], "на главной нет фиктивных результатов")

        later = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        created = client.post(
            "/api/contests",
            headers=auth(organizer_token),
            json={
                "title": "Вечерний тур",
                "description": "Короткий тур для проверки платформы.",
                "start_time": later,
                "duration_minutes": 90,
                "problem_ids": [problems[0]["id"], problems[1]["id"]],
            },
        )
        expect(created.status_code == 200 and created.json()["phase"] == "draft", "организатор создаёт черновик")
        expect(created.json()["participation_format"] == "individual" and created.json()["participant_count"] == 0, "новый турнир индивидуальный")
        contest_id = created.json()["id"]
        expect(client.get("/api/contests").json() == [], "черновик скрыт от гостей")
        edited = client.put(
            f"/api/contests/{contest_id}",
            headers=auth(organizer_token),
            json={
                "title": "Вечерний турнир",
                "description": "Обновлённое описание.",
                "start_time": later,
                "duration_minutes": 90,
                "problem_ids": [problems[0]["id"], problems[1]["id"]],
            },
        )
        expect(edited.status_code == 200 and edited.json()["title"] == "Вечерний турнир", "организатор редактирует черновик")
        published = client.post(f"/api/contests/{contest_id}/publish", headers=auth(organizer_token))
        expect(published.status_code == 200 and published.json()["phase"] == "upcoming", "публикация будущего турнира")

        registered = client.post(f"/api/contests/{contest_id}/register", headers=auth(participant_token))
        expect(registered.status_code == 200 and registered.json()["is_registered"] is True, "регистрация на турнир")
        cancelled = client.delete(f"/api/contests/{contest_id}/register", headers=auth(participant_token))
        expect(cancelled.status_code == 200 and cancelled.json()["is_registered"] is False, "отмена регистрации до старта")
        client.post(f"/api/contests/{contest_id}/register", headers=auth(participant_token))
        early = client.post(
            "/api/submissions",
            headers=auth(participant_token),
            json={
                "problem_id": problems[0]["id"],
                "language": "python",
                "source_code": SOLUTIONS["Сумма двух чисел"],
                "contest_id": contest_id,
            },
        )
        expect(early.status_code == 403, "нельзя сдавать задачу до старта")

        started = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        live = client.post(
            "/api/contests",
            headers=auth(organizer_token),
            json={
                "title": "Идущий турнир",
                "description": "Турнир, который уже начался.",
                "start_time": started,
                "duration_minutes": 120,
                "problem_ids": [problems[0]["id"], problems[2]["id"]],
            },
        )
        live_id = live.json()["id"]
        client.post(f"/api/contests/{live_id}/publish", headers=auth(organizer_token))
        live_view = client.get(f"/api/contests/{live_id}").json()
        expect(live_view["phase"] == "running", "опубликованный турнир со стартом в прошлом идёт")
        expect(len(live_view["problems"]) == 2, "в турнире две задачи")

        locked = client.put(
            f"/api/contests/{live_id}",
            headers=auth(organizer_token),
            json={
                "title": "Попытка изменить",
                "description": "Уже нельзя",
                "start_time": started,
                "duration_minutes": 120,
                "problem_ids": [problems[0]["id"]],
            },
        )
        expect(locked.status_code == 400, "идущий турнир нельзя редактировать")

        second = client.post(
            "/api/auth/register",
            json={"username": "cara", "email": "cara@example.com", "password": "secret123", "role": "participant"},
        )
        cara = second.json()["access_token"]
        expect(client.post(f"/api/contests/{live_id}/register", headers=auth(participant_token)).status_code == 200, "alice в турнире")
        expect(client.post(f"/api/contests/{live_id}/register", headers=auth(cara)).status_code == 200, "cara в турнире")
        expect(client.get(f"/api/contests/{live_id}").json()["participant_count"] == 2, "в турнире два участника")
        expect(
            client.delete(f"/api/contests/{live_id}/register", headers=auth(participant_token)).status_code == 400,
            "после старта регистрацию не отменить",
        )

        blocked = client.post(
            "/api/submissions",
            headers=auth(participant_token),
            json={
                "problem_id": problems[0]["id"],
                "contest_id": live_id,
                "language": "python",
                "source_code": SOLUTIONS["Сумма двух чисел"],
            },
        )
        expect(blocked.status_code == 503, "во время турнира без Judge0 вердикт не выставляется")

        def record_ok(username: str, problem_id: int, contest_id: int, when: datetime) -> None:
            db = SessionLocal()
            try:
                participant = db.query(User).filter(User.username == username).one()
                db.add(
                    Submission(
                        user_id=participant.id,
                        problem_id=problem_id,
                        contest_id=contest_id,
                        language="python",
                        source_code="# запись для таблицы, не вердикт судьи\n",
                        verdict="OK",
                        message="Сохранено для проверки таблицы.",
                        tests_passed=1,
                        tests_total=1,
                        judge_mode="judge0",
                        created_at=when,
                    )
                )
                db.commit()
            finally:
                db.close()

        now = datetime.utcnow()
        record_ok("alice", problems[0]["id"], live_id, now - timedelta(seconds=40))
        record_ok("cara", problems[0]["id"], live_id, now - timedelta(seconds=20))
        record_ok("alice", problems[2]["id"], live_id, now - timedelta(seconds=10))

        table = client.get(f"/api/contests/{live_id}/standings").json()
        expect(len(table) == 2, "в таблице оба участника")
        expect(table[0]["username"] == "alice" and table[0]["solved"] == 2 and table[0]["place"] == 1, "лидер по числу задач")
        expect(table[1]["username"] == "cara" and table[1]["solved"] == 1 and table[1]["place"] == 2, "второе место")
        expect(table[0]["time_seconds"] >= 0, "время посчитано")

        denied = client.post(f"/api/contests/{live_id}/finish", headers=auth(participant_token))
        expect(denied.status_code == 403, "участник не завершает турнир")
        finished_early = client.post(f"/api/contests/{live_id}/finish", headers=auth(organizer_token))
        expect(finished_early.status_code == 200 and finished_early.json()["phase"] == "finished", "организатор завершает турнир досрочно")
        expect(client.get(f"/api/contests/{live_id}/standings").json()[0]["username"] == "alice", "таблица сохраняется после завершения")
        late_submit = client.post(
            "/api/submissions",
            headers=auth(participant_token),
            json={
                "problem_id": problems[0]["id"],
                "contest_id": live_id,
                "language": "python",
                "source_code": SOLUTIONS["Сумма двух чисел"],
            },
        )
        expect(late_submit.status_code == 403, "после завершения решения не принимаются")
        expect(client.post(f"/api/contests/{live_id}/register", headers=auth(organizer_token)).status_code == 400, "на завершённый турнир нельзя записаться")

        team = client.post(
            "/api/contests",
            headers=auth(organizer_token),
            json={
                "title": "Командный кубок",
                "description": "Формат для команд.",
                "start_time": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                "duration_minutes": 60,
                "problem_ids": [problems[0]["id"]],
                "participation_format": "team",
            },
        )
        expect(team.status_code == 200 and team.json()["participation_format"] == "team", "организатор создаёт командный турнир")
        team_id = team.json()["id"]
        client.post(f"/api/contests/{team_id}/publish", headers=auth(organizer_token))
        personal = client.post(f"/api/contests/{team_id}/register", headers=auth(participant_token))
        expect(personal.status_code == 400 and "команд" in personal.json()["detail"], "на командный турнир нельзя записаться лично")
        created_team = client.post(
            "/api/teams",
            headers=auth(participant_token),
            json={
                "name": "Алгоритмы",
                "description": "Пара участников.",
                "specialization": "алгоритмы",
                "max_members": 2,
                "recruiting": True,
            },
        )
        expect(created_team.status_code == 200 and created_team.json()["is_captain"] is True, "участник создаёт команду и становится капитаном")
        algorithms_id = created_team.json()["id"]
        expect(client.post("/api/teams", headers=auth(participant_token), json={"name": "Вторая", "description": "", "specialization": "графы", "max_members": 2}).status_code == 400, "нельзя создать вторую команду")
        applied = client.post(f"/api/teams/{algorithms_id}/applications", headers=auth(cara))
        expect(applied.status_code == 200, "заявка в команду")
        expect(client.post(f"/api/teams/{algorithms_id}/applications", headers=auth(cara)).status_code == 400, "повторная заявка отклоняется")
        captain_view = client.get(f"/api/teams/{algorithms_id}", headers=auth(participant_token)).json()
        application_id = captain_view["applications"][0]["id"]
        accepted = client.post(f"/api/teams/{algorithms_id}/applications/{application_id}/accept", headers=auth(participant_token))
        expect(accepted.status_code == 200 and accepted.json()["member_count"] == 2, "капитан принимает заявку")
        dave_token = client.post("/api/auth/login", json={"email": "dave@example.com", "password": "secret123"}).json()["access_token"]
        expect(client.post(f"/api/teams/{algorithms_id}/applications", headers=auth(dave_token)).status_code == 400, "в полную команду нельзя подать заявку")
        registered_team = client.post(f"/api/contests/{team_id}/register-team", headers=auth(participant_token))
        expect(registered_team.status_code == 200 and registered_team.json()["participant_count"] == 1, "капитан записывает команду")
        expect(client.get(f"/api/contests/{team_id}", headers=auth(cara)).json()["is_registered"] is True, "участник команды тоже записан")
        expect(client.delete(f"/api/contests/{team_id}/register", headers=auth(cara)).status_code == 403, "обычный участник не снимает команду")
        expect(client.delete(f"/api/contests/{team_id}/register", headers=auth(participant_token)).status_code == 200, "капитан снимает команду до старта")
        live_team = client.post(
            "/api/contests",
            headers=auth(organizer_token),
            json={
                "title": "Идущий командный турнир",
                "description": "Таблица команды.",
                "start_time": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
                "duration_minutes": 120,
                "problem_ids": [problems[0]["id"], problems[2]["id"]],
                "participation_format": "team",
            },
        )
        live_team_id = live_team.json()["id"]
        client.post(f"/api/contests/{live_team_id}/publish", headers=auth(organizer_token))
        expect(client.post(f"/api/contests/{live_team_id}/register-team", headers=auth(participant_token)).status_code == 200, "команда записывается на идущий турнир")
        record_ok("alice", problems[0]["id"], live_team_id, datetime.utcnow() - timedelta(seconds=30))
        record_ok("cara", problems[2]["id"], live_team_id, datetime.utcnow() - timedelta(seconds=10))
        team_table = client.get(f"/api/contests/{live_team_id}/standings").json()
        expect(len(team_table) == 1 and team_table[0]["username"] == "Алгоритмы" and team_table[0]["solved"] == 2, "в командной таблице одна строка на команду")
        foreign = client.post(
            "/api/contests",
            headers=auth(participant_token),
            json={
                "title": "Чужая организация",
                "description": "Не должно создаться.",
                "start_time": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
                "duration_minutes": 60,
                "problem_ids": [problems[0]["id"]],
                "organization_id": org_id,
            },
        )
        expect(foreign.status_code == 403, "чужой пользователь не создаёт корпоративный турнир")
        corporate = client.post(
            "/api/contests",
            headers=auth(organizer_token),
            json={
                "title": "Кубок Acme",
                "description": "Турнир организации.",
                "start_time": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
                "duration_minutes": 60,
                "problem_ids": [hidden_id],
                "organization_id": org_id,
            },
        )
        expect(corporate.status_code == 200 and corporate.json()["organization_name"] == "Acme", "организация проводит свой турнир")

        ended = client.post(
            "/api/contests",
            headers=auth(organizer_token),
            json={
                "title": "Прошедший турнир",
                "description": "Уже закончился.",
                "start_time": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
                "duration_minutes": 30,
                "problem_ids": [problems[0]["id"]],
            },
        )
        ended_id = ended.json()["id"]
        client.post(f"/api/contests/{ended_id}/publish", headers=auth(organizer_token))
        closed = client.post(f"/api/contests/{ended_id}/register", headers=auth(participant_token))
        expect(closed.status_code == 400, "на завершённый турнир нельзя зарегистрироваться")
        expect(client.get(f"/api/contests/{ended_id}").json()["phase"] == "finished", "статус завершённого турнира")

        copied = (
            "def warehouse_route(nodes, edges, start, goal):\n"
            "    adjacent = {node: [] for node in nodes}\n"
            "    for left, right, weight in edges:\n"
            "        adjacent[left].append((right, weight))\n"
            "        adjacent[right].append((left, weight))\n"
            "    best = {node: 10 ** 9 for node in nodes}\n"
            "    best[start] = 0\n"
            "    queue = [start]\n"
            "    while queue:\n"
            "        current = queue.pop(0)\n"
            "        for nxt, weight in adjacent[current]:\n"
            "            candidate = best[current] + weight\n"
            "            if candidate < best[nxt]:\n"
            "                best[nxt] = candidate\n"
            "                queue.append(nxt)\n"
            "    return best[goal]\n"
            "print(warehouse_route([1, 2, 3], [(1, 2, 4), (2, 3, 5)], 1, 3))\n"
        )
        commented = "# черновик маршрута\n" + copied.replace("\n", "\n\n")
        other = (
            "def unique_inventory_total(records):\n"
            "    seen = {}\n"
            "    for sku, qty, price in records:\n"
            "        seen[sku] = seen.get(sku, 0) + qty * price\n"
            "    names = sorted(seen)\n"
            "    total = 0\n"
            "    for name in names:\n"
            "        total += seen[name]\n"
            "    return total\n"
            "print(unique_inventory_total([('bolt', 2, 15), ('nut', 4, 3)]))\n"
        )
        short = "a, b = map(int, input().split())\nprint(a + b)\n"
        fair = client.post(
            "/api/contests",
            headers=auth(organizer_token),
            json={
                "title": "Проверка FairPlay",
                "description": "Сравнение решений.",
                "start_time": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
                "duration_minutes": 90,
                "problem_ids": [problems[0]["id"], problems[1]["id"]],
                "participation_format": "team",
                "organization_id": org_id,
            },
        )
        expect(fair.status_code == 200, "турнир для FairPlay создан")
        fair_id = fair.json()["id"]
        client.post(f"/api/contests/{fair_id}/publish", headers=auth(organizer_token))
        dave_team = client.post(
            "/api/teams",
            headers=auth(dave_token),
            json={"name": "Склад", "description": "Вторая команда", "specialization": "графы", "max_members": 3, "recruiting": True},
        )
        expect(dave_team.status_code == 200, "вторая команда для сравнения")
        eva = client.post("/api/auth/register", json={"username": "eva", "email": "eva@example.com", "password": "secret123"})
        eva_token = eva.json()["access_token"]
        eva_apply = client.post(f"/api/teams/{dave_team.json()['id']}/applications", headers=auth(eva_token))
        expect(eva_apply.status_code == 200, "заявка во вторую команду")
        captain_team = client.get(f"/api/teams/{dave_team.json()['id']}", headers=auth(dave_token)).json()
        client.post(
            f"/api/teams/{dave_team.json()['id']}/applications/{captain_team['applications'][0]['id']}/accept",
            headers=auth(dave_token),
        )
        expect(client.post(f"/api/contests/{fair_id}/register-team", headers=auth(participant_token)).status_code == 200, "первая команда в турнире FairPlay")
        expect(client.post(f"/api/contests/{fair_id}/register-team", headers=auth(dave_token)).status_code == 200, "вторая команда в турнире FairPlay")

        def save_source(username: str, problem_id: int, source: str) -> None:
            db = SessionLocal()
            try:
                person = db.query(User).filter(User.username == username).one()
                db.add(
                    Submission(
                        user_id=person.id,
                        problem_id=problem_id,
                        contest_id=fair_id,
                        language="python",
                        source_code=source,
                        verdict="OK",
                        message="Решение для сравнения.",
                        tests_passed=1,
                        tests_total=1,
                        judge_mode="judge0",
                        created_at=datetime.utcnow(),
                    )
                )
                db.commit()
            finally:
                db.close()

        save_source("alice", problems[0]["id"], copied)
        save_source("cara", problems[0]["id"], copied)
        save_source("dave", problems[0]["id"], commented)
        save_source("eva", problems[0]["id"], other)
        save_source("alice", problems[1]["id"], short)
        save_source("dave", problems[1]["id"], short)
        idle = client.get(f"/api/contests/{fair_id}/fairplay", headers=auth(organizer_token))
        expect(idle.status_code == 200 and idle.json()["analyzed_at"] is None and idle.json()["participants"] == [] and idle.json()["reports"] == [], "до анализа отчётов FairPlay нет")
        expect(client.get(f"/api/contests/{fair_id}/fairplay", headers=auth(participant_token)).status_code == 403, "участник не открывает FairPlay")
        expect(client.get(f"/api/contests/{fair_id}/fairplay", headers=auth(dave_token)).status_code == 200, "сотрудник организации открывает FairPlay своего турнира")
        analyzed = client.post(f"/api/contests/{fair_id}/fairplay", headers=auth(organizer_token))
        expect(analyzed.status_code == 200 and analyzed.json()["analyzed_at"], "анализ FairPlay выполнен")
        pairs = {(row["username"], row["matched_username"]) for row in analyzed.json()["reports"]}
        expect(("alice", "cara") not in pairs and ("cara", "alice") not in pairs, "решения одной команды не сравниваются")
        expect(("alice", "dave") in pairs and ("cara", "dave") in pairs, "похожее решение другой команды отмечено")
        expect(all(row["similarity_percent"] >= 70 for row in analyzed.json()["reports"]), "в отчёте только заметное сходство")
        expect(len(analyzed.json()["reports"]) == 2, "короткие типовые решения не попадают в отчёт")
        eva_row = next(row for row in analyzed.json()["participants"] if row["username"] == "eva")
        expect(eva_row["status"] == "clear" and eva_row["match_count"] == 0 and eva_row["submission_count"] == 1, "после анализа уникальное решение без совпадений")
        alice_row = next(row for row in analyzed.json()["participants"] if row["username"] == "alice")
        expect(alice_row["status"] == "attention" and alice_row["solved_count"] == 2 and "dave" in alice_row["matched_usernames"], "сводка участника со совпадениями")
        report_id = next(row["id"] for row in analyzed.json()["reports"] if row["username"] == "alice")
        detail = client.get(f"/api/contests/{fair_id}/fairplay/reports/{report_id}", headers=auth(organizer_token))
        expect(detail.status_code == 200 and detail.json()["fragments"] and "списыван" in detail.json()["explanation"], "отчёт показывает совпавшие фрагменты и пояснение")
        expect(client.get(f"/api/contests/{fair_id}/fairplay/reports/{report_id}", headers=auth(participant_token)).status_code == 403, "участник не читает чужой код")
        reviewed = client.post(f"/api/contests/{fair_id}/fairplay/reports/{report_id}/review", headers=auth(organizer_token))
        expect(reviewed.status_code == 200 and reviewed.json()["status"] == "reviewed", "организатор отмечает отчёт проверенным")
        expect(client.get(f"/api/contests/{fair_id}/standings").status_code == 200, "проверка FairPlay не меняет таблицу")

        protocol = client.post(
            "/api/contests",
            headers=auth(organizer_token),
            json={
                "title": "Итоговый протокол",
                "description": "Документ по результатам.",
                "start_time": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
                "duration_minutes": 120,
                "problem_ids": [problems[0]["id"]],
                "organization_id": org_id,
            },
        )
        protocol_id = protocol.json()["id"]
        client.post(f"/api/contests/{protocol_id}/publish", headers=auth(organizer_token))
        expect(client.post(f"/api/contests/{protocol_id}/register", headers=auth(participant_token)).status_code == 200, "участник в турнире для отчёта")
        profile = client.patch(
            "/api/auth/profile",
            headers=auth(participant_token),
            json={"full_name": "Алиса Иванова", "birth_date": "2004-05-06"},
        )
        expect(profile.status_code == 200 and profile.json()["full_name"] == "Алиса Иванова", "участник сохраняет ФИО")
        expect(client.patch("/api/auth/profile", headers=auth(participant_token), json={"full_name": "Алиса Иванова", "birth_date": "1890-01-01"}).status_code == 400, "слишком ранняя дата рождения отклоняется")
        record_ok("alice", problems[0]["id"], protocol_id, datetime.utcnow())
        expect(client.post(f"/api/contests/{protocol_id}/reports", headers=auth(organizer_token), json={"report_format": "csv"}).status_code == 400, "до завершения турнира отчёт не формируется")
        expect(client.post(f"/api/contests/{protocol_id}/finish", headers=auth(organizer_token)).status_code == 200, "турнир для отчёта завершён")
        csv_report = client.post(f"/api/contests/{protocol_id}/reports", headers=auth(organizer_token), json={"report_format": "csv"})
        xlsx_report = client.post(f"/api/contests/{protocol_id}/reports", headers=auth(organizer_token), json={"report_format": "xlsx"})
        pdf_report = client.post(f"/api/contests/{protocol_id}/reports", headers=auth(organizer_token), json={"report_format": "pdf"})
        expect(csv_report.status_code == 200 and xlsx_report.status_code == 200 and pdf_report.status_code == 200, "организатор формирует CSV, XLSX и PDF")
        listed = client.get(f"/api/contests/{protocol_id}/reports", headers=auth(organizer_token))
        expect(listed.status_code == 200 and len(listed.json()) == 3, "список хранит имена сформированных файлов")
        downloaded = client.get(f"/api/contests/{protocol_id}/reports/{csv_report.json()['id']}/download", headers=auth(organizer_token))
        csv_text = downloaded.content.decode("utf-8-sig")
        expect(downloaded.status_code == 200 and "Итоговый протокол" in csv_text and "Алиса Иванова" in csv_text and "2004-05-06" in csv_text, "CSV содержит турнир и данные участника")
        expect("Дисквалификации не зафиксированы" in csv_text and "спортивного разряда" in csv_text, "в отчёте нет выдуманных дисквалификаций и есть оговорка")
        expect(client.get(f"/api/contests/{protocol_id}/reports/{csv_report.json()['id']}/download", headers=auth(participant_token)).status_code == 403, "участник не скачивает отчёт")
        from openpyxl import load_workbook
        from app.contest_reports import report_file

        sheet = load_workbook(report_file(xlsx_report.json()["file_name"])).active
        expect(sheet["A1"].value == "Итоговый протокол", "XLSX открывается и содержит название")
        pdf_bytes = client.get(f"/api/contests/{protocol_id}/reports/{pdf_report.json()['id']}/download", headers=auth(organizer_token)).content
        expect(pdf_bytes.startswith(b"%PDF") and len(pdf_bytes) > 500, "PDF сформирован")
        expect(client.post(f"/api/contests/{live_team_id}/finish", headers=auth(organizer_token)).status_code == 200, "командный турнир завершён для отчёта")
        team_csv = client.post(f"/api/contests/{live_team_id}/reports", headers=auth(organizer_token), json={"report_format": "csv"})
        team_text = client.get(f"/api/contests/{live_team_id}/reports/{team_csv.json()['id']}/download", headers=auth(organizer_token)).content.decode("utf-8-sig")
        expect(team_csv.status_code == 200 and "Алгоритмы" in team_text and "alice" in team_text, "командный отчёт содержит команду и состав")

        os.environ["ADMIN_EMAIL"] = "root@example.com"
        os.environ["ADMIN_PASSWORD"] = "secret123"
        os.environ["ADMIN_USERNAME"] = "root"
        from app.bootstrap import ensure_admin

        db = SessionLocal()
        try:
            ensure_admin(db)
        finally:
            db.close()
        root = client.post("/api/auth/login", json={"email": "root@example.com", "password": "secret123"})
        expect(root.status_code == 200 and root.json()["user"]["role"] == "admin", "администратор из окружения")
        root_token = root.json()["access_token"]
        users = client.get("/api/admin/users", headers=auth(root_token))
        expect(users.status_code == 200 and any(row["username"] == "alice" for row in users.json()), "администратор видит пользователей")
        organizations = client.get("/api/admin/organizations", headers=auth(root_token))
        expect(organizations.status_code == 200 and any(row["name"] == "Acme" for row in organizations.json()), "администратор видит организации")
        alice_id = next(row["id"] for row in users.json() if row["username"] == "alice")
        promoted = client.patch(f"/api/admin/users/{alice_id}", headers=auth(root_token), json={"role": "organizer"})
        expect(promoted.status_code == 200 and promoted.json()["can_organize"] is True, "администратор назначает организатора")
        demoted = client.patch(f"/api/admin/users/{root.json()['user']['id']}", headers=auth(root_token), json={"role": "participant"})
        expect(demoted.status_code == 400, "единственного администратора нельзя снять")

        waiting_duel = client.post("/api/matches/queue", headers=auth(participant_token), json={"mode": "duel"})
        expect(waiting_duel.status_code == 200 and waiting_duel.json()["state"] == "waiting", "участник встаёт в очередь дуэли")
        paired = client.post("/api/matches/queue", headers=auth(cara), json={"mode": "duel"})
        expect(paired.status_code == 200 and paired.json()["state"] == "live" and len(paired.json()["match"]["players"]) == 2, "автоподбор собирает дуэль 1 на 1")
        duel_id = paired.json()["match"]["id"]
        duel_tasks = paired.json()["match"]["tasks"]
        presence = client.post(
            f"/api/matches/{duel_id}/presence",
            headers=auth(participant_token),
            json={"problem_id": duel_tasks[0]["problem_id"], "stage": "coding"},
        )
        expect(presence.status_code == 200 and presence.json()["players"][0]["stage"] == "coding", "соперник видит этап написания кода")
        expect(client.get(f"/api/matches/{duel_id}", headers=auth(dave_token)).status_code == 403, "посторонний не открывает дуэль")
        db = SessionLocal()
        try:
            alice = db.query(User).filter(User.username == "alice").one()
            for task in duel_tasks:
                db.add(
                    Submission(
                        user_id=alice.id,
                        problem_id=task["problem_id"],
                        match_id=duel_id,
                        language="python",
                        source_code="print(1)\n",
                        verdict="OK",
                        message="Решение для завершения дуэли.",
                        tests_passed=1,
                        tests_total=1,
                        judge_mode="judge0",
                        created_at=datetime.utcnow(),
                    )
                )
            db.commit()
            from app.arena import settle_match

            settle_match(db, duel_id)
        finally:
            db.close()
        finished_duel = client.get(f"/api/matches/{duel_id}", headers=auth(cara))
        expect(finished_duel.status_code == 200 and finished_duel.json()["status"] == "finished" and finished_duel.json()["winner_name"] == "alice", "дуэль останавливается, когда один участник решил все задачи")
        room = client.post(
            "/api/matches",
            headers=auth(organizer_token),
            json={
                "mode": "team",
                "tasks": [
                    {"problem_id": problems[0]["id"], "assignee_role": 0},
                    {"problem_id": problems[1]["id"], "assignee_role": 1},
                ],
            },
        )
        expect(room.status_code == 200 and room.json()["status"] == "waiting" and room.json()["invite_code"], "организатор создаёт командный матч и ссылку")
        invite = room.json()["invite_code"]
        expect(client.post(f"/api/matches/join/{invite}", headers=auth(dave_token)).status_code == 200, "напарник входит по ссылке")
        expect(client.post(f"/api/matches/join/{invite}", headers=auth(eva_token)).status_code == 200, "соперник входит по ссылке")
        fox = client.post("/api/auth/register", json={"username": "fox", "email": "fox@example.com", "password": "secret123"})
        filled = client.post(f"/api/matches/join/{invite}", headers=auth(fox.json()["access_token"]))
        expect(filled.status_code == 200 and filled.json()["status"] == "live" and filled.json()["mode"] == "team", "командный матч 2 на 2 начинается, когда заняты четыре места")
        denied_task = client.post(
            "/api/submissions",
            headers=auth(dave_token),
            json={"problem_id": problems[0]["id"], "language": "python", "source_code": "print(1)\n", "match_id": room.json()["id"]},
        )
        expect(denied_task.status_code == 403, "задачу решает участник, которого назначил организатор")

    with TestClient(app) as again:
        saved = again.post("/api/auth/login", json={"email": "alice@example.com", "password": "secret123"})
        expect(saved.status_code == 200 and saved.json()["user"]["full_name"] == "Алиса Иванова", "учётная запись сохраняется в базе")
        catalog = again.get("/api/problems")
        expect(catalog.status_code == 200 and len(catalog.json()) >= 9, "каталог сохраняется в базе")

    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
