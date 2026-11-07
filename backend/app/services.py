from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import Contest, ContestProblem, Problem, Registration, Submission, Team, User


def isoformat_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat()


def as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def phase_of(contest: Contest, now: Optional[datetime] = None) -> str:
    if contest.status != "published":
        return "draft"
    if contest.manually_finished:
        return "finished"
    current = now or datetime.utcnow()
    end = contest.start_time + timedelta(minutes=contest.duration_minutes)
    if current < contest.start_time:
        return "upcoming"
    if current >= end:
        return "finished"
    return "running"


def problem_letter(index: int) -> str:
    if 0 <= index < 26:
        return chr(ord("A") + index)
    return str(index + 1)


def clip(value: Optional[str], limit: int = 1500) -> Optional[str]:
    if value is None:
        return None
    text = value.replace("\r\n", "\n")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n… (обрезано)"


def normalize_output(value: str) -> str:
    text = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    return "\n".join(line.rstrip() for line in text.split("\n"))


def is_registered(db: Session, contest_id: int, user_id: Optional[int]) -> bool:
    if user_id is None:
        return False
    return (
        db.query(Registration)
        .filter(Registration.contest_id == contest_id, Registration.user_id == user_id)
        .first()
        is not None
    )


def solved_problem_ids(db: Session, user_id: Optional[int], contest_id: Optional[int] = None) -> set[int]:
    if user_id is None:
        return set()
    query = db.query(Submission.problem_id).filter(Submission.user_id == user_id, Submission.verdict == "OK")
    if contest_id is None:
        rows = query.distinct().all()
    else:
        rows = query.filter(Submission.contest_id == contest_id).distinct().all()
    return {row[0] for row in rows}


def ensure_owner(user: User, contest: Contest) -> None:
    if user.role == "admin" or contest.organizer_id == user.id:
        return
    raise HTTPException(status_code=403, detail="Недостаточно прав для изменения соревнования")


def ensure_editable(contest: Contest) -> None:
    phase = phase_of(contest)
    if phase in ("running", "finished"):
        raise HTTPException(status_code=400, detail="Нельзя изменять соревнование после его начала")


def replace_contest_problems(db: Session, contest: Contest, problem_ids: list[int]) -> None:
    unique: list[int] = []
    for problem_id in problem_ids:
        if problem_id not in unique:
            unique.append(problem_id)
    found = db.query(Problem.id).filter(Problem.id.in_(unique)).all()
    found_ids = {row[0] for row in found}
    if len(found_ids) != len(unique):
        raise HTTPException(status_code=400, detail="Выбраны несуществующие задачи")
    db.expire(contest, ["contest_problems"])
    existing = db.query(ContestProblem).filter(ContestProblem.contest_id == contest.id).all()
    for row in existing:
        db.delete(row)
    db.flush()
    for index, problem_id in enumerate(unique):
        db.add(ContestProblem(contest_id=contest.id, problem_id=problem_id, order_index=index))


def visible_contest(contest: Contest, user: Optional[User]) -> bool:
    if contest.status == "published":
        return True
    if user is None:
        return False
    return user.role == "admin" or user.id == contest.organizer_id


def contest_end(contest: Contest) -> datetime:
    return contest.start_time + timedelta(minutes=contest.duration_minutes)


def build_standings(db: Session, contest: Contest) -> list[dict]:
    if contest.participation_format == "team":
        return _team_standings(db, contest)
    return _individual_standings(db, contest)


def _individual_standings(db: Session, contest: Contest) -> list[dict]:
    end = contest_end(contest)
    problem_ids = {link.problem_id for link in contest.contest_problems}
    registrations = (
        db.query(Registration, User)
        .join(User, User.id == Registration.user_id)
        .filter(Registration.contest_id == contest.id)
        .all()
    )
    rows = []
    for _registration, participant in registrations:
        submissions = (
            db.query(Submission)
            .filter(
                Submission.user_id == participant.id,
                Submission.contest_id == contest.id,
                Submission.verdict == "OK",
                Submission.created_at >= contest.start_time,
                Submission.created_at <= end,
            )
            .order_by(Submission.created_at.asc())
            .all()
        )
        first_ok: dict[int, Submission] = {}
        for submission in submissions:
            if submission.problem_id in problem_ids and submission.problem_id not in first_ok:
                first_ok[submission.problem_id] = submission
        time_seconds = 0
        for submission in first_ok.values():
            time_seconds += max(0, int((submission.created_at - contest.start_time).total_seconds()))
        rows.append(
            {
                "user_id": participant.id,
                "username": participant.username,
                "solved": len(first_ok),
                "time_seconds": time_seconds if first_ok else 0,
            }
        )
    return _assign_places(rows)


def _team_standings(db: Session, contest: Contest) -> list[dict]:
    end = contest_end(contest)
    problem_ids = {link.problem_id for link in contest.contest_problems}
    registrations = db.query(Registration).filter(Registration.contest_id == contest.id, Registration.team_id.isnot(None)).all()
    by_team: dict[int, list[int]] = {}
    for registration in registrations:
        by_team.setdefault(registration.team_id, []).append(registration.user_id)
    rows = []
    for team_id, user_ids in by_team.items():
        team = db.get(Team, team_id)
        if team is None:
            continue
        submissions = (
            db.query(Submission)
            .filter(
                Submission.user_id.in_(user_ids),
                Submission.contest_id == contest.id,
                Submission.verdict == "OK",
                Submission.created_at >= contest.start_time,
                Submission.created_at <= end,
            )
            .order_by(Submission.created_at.asc())
            .all()
        )
        first_ok: dict[int, Submission] = {}
        for submission in submissions:
            if submission.problem_id in problem_ids and submission.problem_id not in first_ok:
                first_ok[submission.problem_id] = submission
        time_seconds = 0
        for submission in first_ok.values():
            time_seconds += max(0, int((submission.created_at - contest.start_time).total_seconds()))
        rows.append(
            {
                "user_id": team.captain_id,
                "username": team.name,
                "team_id": team.id,
                "solved": len(first_ok),
                "time_seconds": time_seconds if first_ok else 0,
            }
        )
    return _assign_places(rows)


def _assign_places(rows: list[dict]) -> list[dict]:
    rows.sort(key=lambda row: (-row["solved"], row["time_seconds"], row["username"].lower()))
    place = 0
    previous = None
    for index, row in enumerate(rows, start=1):
        key = (row["solved"], row["time_seconds"])
        if key != previous:
            place = index
            previous = key
        row["place"] = place
    return rows
