from __future__ import annotations

import secrets
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from .models import ArenaMatch, ArenaPresence, ArenaQueue, ArenaSeat, ArenaTask, Problem, Submission, User
from .services import isoformat_utc

CAPACITY = {"duel": 2, "team": 4}
TEAM_NAME = {0: "Команда 1", 1: "Команда 2"}


def _code() -> str:
    return secrets.token_hex(4)


def _capacity(mode: str) -> int:
    if mode not in CAPACITY:
        raise HTTPException(status_code=400, detail="Неизвестный режим матча")
    return CAPACITY[mode]


def _team_index(slot: int) -> int:
    return 0 if slot < 2 else 1


def _role_in_team(slot: int) -> int:
    return slot % 2


def active_match(db: Session, user_id: int) -> Optional[ArenaMatch]:
    seat = (
        db.query(ArenaSeat)
        .join(ArenaMatch, ArenaMatch.id == ArenaSeat.match_id)
        .filter(ArenaSeat.user_id == user_id, ArenaMatch.status.in_(("waiting", "live")))
        .first()
    )
    return seat.match if seat is not None else None


def _published_problems(db: Session, problem_ids: list[int]) -> list[Problem]:
    if not problem_ids:
        raise HTTPException(status_code=400, detail="Выберите хотя бы одну задачу")
    found = {
        problem.id: problem
        for problem in db.query(Problem)
        .filter(Problem.id.in_(problem_ids), Problem.publication_status == "published", Problem.kind == "algorithmic")
        .all()
    }
    ordered = []
    for problem_id in problem_ids:
        problem = found.get(problem_id)
        if problem is None:
            raise HTTPException(status_code=400, detail="В матч можно взять только опубликованные алгоритмические задачи")
        ordered.append(problem)
    return ordered


def default_problem_ids(db: Session) -> list[int]:
    rows = (
        db.query(Problem.id)
        .filter(Problem.publication_status == "published", Problem.kind == "algorithmic")
        .order_by(Problem.id.asc())
        .limit(2)
        .all()
    )
    if len(rows) < 1:
        raise HTTPException(status_code=400, detail="Нет опубликованных задач для матча")
    return [row[0] for row in rows]


def _add_tasks(db: Session, match: ArenaMatch, problem_ids: list[int], roles: Optional[list[Optional[int]]]) -> None:
    problems = _published_problems(db, problem_ids)
    for index, problem in enumerate(problems):
        role = None
        if match.mode == "team":
            role = 0 if roles is None or index >= len(roles) or roles[index] is None else roles[index]
            if role not in (0, 1):
                raise HTTPException(status_code=400, detail="Для каждой задачи укажите участника 1 или 2")
        db.add(ArenaTask(match_id=match.id, problem_id=problem.id, order_index=index, assignee_role=role))


def _open_seats(db: Session, match: ArenaMatch) -> None:
    for slot in range(_capacity(match.mode)):
        db.add(ArenaSeat(match_id=match.id, slot=slot, user_id=None))


def create_match(
    db: Session,
    organizer: User,
    mode: str,
    problem_ids: list[int],
    roles: Optional[list[Optional[int]]] = None,
) -> ArenaMatch:
    _capacity(mode)
    if active_match(db, organizer.id) is not None:
        raise HTTPException(status_code=400, detail="Сначала завершите текущий матч")
    db.query(ArenaQueue).filter(ArenaQueue.user_id == organizer.id).delete(synchronize_session=False)
    match = ArenaMatch(mode=mode, status="waiting", organizer_id=organizer.id, invite_code=_code())
    db.add(match)
    db.flush()
    _add_tasks(db, match, problem_ids, roles)
    _open_seats(db, match)
    db.flush()
    _take_seat(db, match, organizer)
    db.commit()
    return _load(db, match.id)


def _take_seat(db: Session, match: ArenaMatch, user: User) -> None:
    seats = db.query(ArenaSeat).filter(ArenaSeat.match_id == match.id).order_by(ArenaSeat.slot.asc()).all()
    if any(seat.user_id == user.id for seat in seats):
        return
    other = active_match(db, user.id)
    if other is not None and other.id != match.id:
        raise HTTPException(status_code=400, detail="Сначала завершите текущий матч")
    free = [seat for seat in seats if seat.user_id is None]
    if not free:
        raise HTTPException(status_code=400, detail="В этом матче больше нет мест")
    free[0].user_id = user.id
    filled = sum(1 for seat in seats if seat.user_id is not None)
    if filled >= _capacity(match.mode) and match.status == "waiting":
        match.status = "live"
        match.started_at = datetime.utcnow()


def join_match(db: Session, user: User, invite_code: str) -> ArenaMatch:
    match = db.query(ArenaMatch).options(joinedload(ArenaMatch.seats)).filter(ArenaMatch.invite_code == invite_code).first()
    if match is None:
        raise HTTPException(status_code=404, detail="Приглашение не найдено")
    if match.status == "finished":
        raise HTTPException(status_code=400, detail="Этот матч уже завершён")
    db.query(ArenaQueue).filter(ArenaQueue.user_id == user.id).delete(synchronize_session=False)
    _take_seat(db, match, user)
    db.commit()
    return _load(db, match.id)


def _start_from_queue(db: Session, mode: str, users: list[User]) -> ArenaMatch:
    problem_ids = default_problem_ids(db)
    roles = [index % 2 for index in range(len(problem_ids))] if mode == "team" else None
    organizer = users[0]
    match = ArenaMatch(mode=mode, status="live", organizer_id=organizer.id, invite_code=_code(), started_at=datetime.utcnow())
    db.add(match)
    db.flush()
    _add_tasks(db, match, problem_ids, roles)
    for slot in range(_capacity(mode)):
        db.add(ArenaSeat(match_id=match.id, slot=slot, user_id=users[slot].id if slot < len(users) else None))
    db.query(ArenaQueue).filter(ArenaQueue.user_id.in_([user.id for user in users])).delete(synchronize_session=False)
    db.commit()
    return _load(db, match.id)


def enqueue(db: Session, user: User, mode: str) -> dict:
    _capacity(mode)
    current = active_match(db, user.id)
    if current is not None:
        raise HTTPException(status_code=400, detail="Сначала завершите текущий матч")
    existing = db.get(ArenaQueue, user.id)
    if existing is None:
        db.add(ArenaQueue(user_id=user.id, mode=mode))
        db.commit()
    elif existing.mode != mode:
        existing.mode = mode
        existing.created_at = datetime.utcnow()
        db.commit()
    needed = _capacity(mode)
    waiting = db.query(ArenaQueue).filter(ArenaQueue.mode == mode).order_by(ArenaQueue.created_at.asc(), ArenaQueue.user_id.asc()).all()
    if len(waiting) < needed or user.id not in {row.user_id for row in waiting[:needed]}:
        return {"state": "waiting", "mode": mode, "waiting_count": len(waiting), "needed": needed, "match": None}
    people = [db.get(User, row.user_id) for row in waiting[:needed]]
    if any(person is None for person in people):
        raise HTTPException(status_code=400, detail="Не удалось подобрать участников")
    match = _start_from_queue(db, mode, people)
    return {"state": "live", "mode": mode, "waiting_count": 0, "needed": needed, "match": serialize_match(db, match, user)}


def leave_queue(db: Session, user: User) -> None:
    db.query(ArenaQueue).filter(ArenaQueue.user_id == user.id).delete(synchronize_session=False)
    db.commit()


def set_presence(db: Session, user: User, match_id: int, problem_id: int, stage: str) -> ArenaMatch:
    match = _load(db, match_id)
    if match.status != "live":
        raise HTTPException(status_code=400, detail="Матч ещё не идёт")
    if not any(seat.user_id == user.id for seat in match.seats):
        raise HTTPException(status_code=403, detail="Вы не участвуете в этом матче")
    if stage not in ("coding", "fixing"):
        raise HTTPException(status_code=400, detail="Неизвестный этап решения")
    if not any(task.problem_id == problem_id for task in match.tasks):
        raise HTTPException(status_code=400, detail="Этой задачи нет в матче")
    presence = db.query(ArenaPresence).filter(ArenaPresence.match_id == match.id, ArenaPresence.user_id == user.id).first()
    if presence is None:
        presence = ArenaPresence(match_id=match.id, user_id=user.id, problem_id=problem_id, stage=stage)
        db.add(presence)
    else:
        presence.problem_id = problem_id
        presence.stage = stage
        presence.updated_at = datetime.utcnow()
    db.commit()
    return _load(db, match.id)


def ensure_match_submission(db: Session, user: User, problem: Problem, match_id: int) -> ArenaMatch:
    match = _load(db, match_id)
    if match.status != "live":
        raise HTTPException(status_code=403, detail="Матч остановлен")
    seat = next((item for item in match.seats if item.user_id == user.id), None)
    if seat is None:
        raise HTTPException(status_code=403, detail="Вы не участвуете в этом матче")
    task = next((item for item in match.tasks if item.problem_id == problem.id), None)
    if task is None:
        raise HTTPException(status_code=400, detail="Этой задачи нет в матче")
    if match.mode == "team" and task.assignee_role is not None and _role_in_team(seat.slot) != task.assignee_role:
        raise HTTPException(status_code=403, detail="Эту задачу по порядку решает другой участник команды")
    return match


def register_match_verdict(db: Session, match: ArenaMatch, user: User, problem: Problem, verdict: str) -> None:
    stage = "fixing" if verdict != "OK" else "coding"
    presence = db.query(ArenaPresence).filter(ArenaPresence.match_id == match.id, ArenaPresence.user_id == user.id).first()
    if presence is None:
        db.add(ArenaPresence(match_id=match.id, user_id=user.id, problem_id=problem.id, stage=stage))
    else:
        presence.problem_id = problem.id
        presence.stage = stage
        presence.updated_at = datetime.utcnow()
    if verdict == "OK":
        _settle(db, match)
    db.commit()


def settle_match(db: Session, match_id: int) -> None:
    match = _load(db, match_id)
    _settle(db, match)
    db.commit()


def _solved_by_user(db: Session, match: ArenaMatch) -> dict[int, set[int]]:
    problem_ids = {task.problem_id for task in match.tasks}
    rows = (
        db.query(Submission)
        .filter(Submission.match_id == match.id, Submission.verdict == "OK", Submission.problem_id.in_(problem_ids))
        .all()
    )
    solved: dict[int, set[int]] = {}
    for row in rows:
        solved.setdefault(row.user_id, set()).add(row.problem_id)
    return solved


def _settle(db: Session, match: ArenaMatch) -> None:
    if match.status != "live":
        return
    problem_ids = {task.problem_id for task in match.tasks}
    if not problem_ids:
        return
    solved = _solved_by_user(db, match)
    if match.mode == "duel":
        for seat in match.seats:
            if seat.user_id is None or seat.user is None:
                continue
            if problem_ids.issubset(solved.get(seat.user_id, set())):
                match.status = "finished"
                match.finished_at = datetime.utcnow()
                match.winner_name = seat.user.username
                return
        return
    for team_index in (0, 1):
        member_ids = [seat.user_id for seat in match.seats if seat.user_id is not None and _team_index(seat.slot) == team_index]
        union: set[int] = set()
        for member_id in member_ids:
            union |= solved.get(member_id, set())
        if problem_ids.issubset(union):
            match.status = "finished"
            match.finished_at = datetime.utcnow()
            match.winner_name = TEAM_NAME[team_index]
            return


def _load(db: Session, match_id: int) -> ArenaMatch:
    match = (
        db.query(ArenaMatch)
        .options(joinedload(ArenaMatch.seats).joinedload(ArenaSeat.user), joinedload(ArenaMatch.tasks).joinedload(ArenaTask.problem))
        .filter(ArenaMatch.id == match_id)
        .first()
    )
    if match is None:
        raise HTTPException(status_code=404, detail="Матч не найден")
    return match


def _clock(match: ArenaMatch, moment: datetime) -> int:
    if match.started_at is None:
        return 0
    end = match.finished_at or moment
    return max(0, int((end - match.started_at).total_seconds()))


def serialize_match(db: Session, match: ArenaMatch, viewer: User) -> dict:
    now = datetime.utcnow()
    problem_ids = [task.problem_id for task in sorted(match.tasks, key=lambda item: item.order_index)]
    first_ok: dict[tuple[int, int], datetime] = {}
    if problem_ids:
        rows = (
            db.query(Submission)
            .filter(Submission.match_id == match.id, Submission.verdict == "OK", Submission.problem_id.in_(problem_ids))
            .order_by(Submission.created_at.asc())
            .all()
        )
        for row in rows:
            first_ok.setdefault((row.user_id, row.problem_id), row.created_at)
    presence_rows = db.query(ArenaPresence).filter(ArenaPresence.match_id == match.id).all()
    presence = {row.user_id: row for row in presence_rows}
    my_seat = next((seat for seat in match.seats if seat.user_id == viewer.id), None)

    def player_payload(seat: ArenaSeat) -> dict:
        user = seat.user
        current = presence.get(seat.user_id) if seat.user_id is not None else None
        times = []
        for task in sorted(match.tasks, key=lambda item: item.order_index):
            solved_at = first_ok.get((seat.user_id, task.problem_id)) if seat.user_id is not None else None
            times.append(
                {
                    "problem_id": task.problem_id,
                    "seconds": max(0, int((solved_at - match.started_at).total_seconds())) if solved_at and match.started_at else None,
                }
            )
        return {
            "slot": seat.slot,
            "user_id": seat.user_id,
            "username": user.username if user is not None else None,
            "team_index": _team_index(seat.slot),
            "role": _role_in_team(seat.slot),
            "stage": current.stage if current is not None else "coding",
            "problem_id": current.problem_id if current is not None else None,
            "times": times,
        }

    tasks = [
        {
            "problem_id": task.problem_id,
            "title": task.problem.title if task.problem is not None else "",
            "order_index": task.order_index,
            "assignee_role": task.assignee_role,
        }
        for task in sorted(match.tasks, key=lambda item: item.order_index)
    ]
    return {
        "id": match.id,
        "mode": match.mode,
        "status": match.status,
        "invite_code": match.invite_code,
        "organizer_id": match.organizer_id,
        "winner_name": match.winner_name,
        "started_at": isoformat_utc(match.started_at) if match.started_at else None,
        "finished_at": isoformat_utc(match.finished_at) if match.finished_at else None,
        "elapsed_seconds": _clock(match, now),
        "my_slot": my_seat.slot if my_seat is not None else None,
        "tasks": tasks,
        "players": [player_payload(seat) for seat in sorted(match.seats, key=lambda item: item.slot)],
    }
