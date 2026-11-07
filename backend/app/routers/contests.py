from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_user, get_optional_user, require_organizer
from ..models import Contest, ContestProblem, OrganizationMember, Problem, Registration, Team, TeamMember, User
from ..schemas import ContestIn, ContestOut, ContestProblemOut, StandingOut
from ..services import (
    as_naive_utc,
    build_standings,
    ensure_editable,
    ensure_owner,
    isoformat_utc,
    phase_of,
    problem_letter,
    replace_contest_problems,
    is_registered,
    solved_problem_ids,
    visible_contest,
)

router = APIRouter(prefix="/contests", tags=["contests"])


def _organization_for_user(db: Session, user: User, organization_id: Optional[int]) -> Optional[int]:
    if organization_id is None:
        return None
    member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user.id,
            OrganizationMember.member_role.in_(("owner", "organizer")),
        )
        .first()
    )
    if member is None:
        raise HTTPException(status_code=403, detail="Нельзя проводить турнир от имени этой организации")
    return organization_id


def _ensure_problem_selection(db: Session, problem_ids: list[int], organization_id: Optional[int]) -> None:
    unique: list[int] = []
    for problem_id in problem_ids:
        if problem_id not in unique:
            unique.append(problem_id)
    problems = db.query(Problem).filter(Problem.id.in_(unique)).all()
    if len(problems) != len(unique):
        raise HTTPException(status_code=400, detail="Выбраны несуществующие задачи")
    for problem in problems:
        if problem.publication_status != "published":
            raise HTTPException(status_code=400, detail="В турнир можно добавить только опубликованные задачи")
        if problem.kind == "production" and problem.organization_id != organization_id:
            raise HTTPException(status_code=400, detail="Производственную задачу можно добавить только в турнир её организации")


def _load_contest(db: Session, contest_id: int) -> Contest:
    contest = (
        db.query(Contest)
        .options(
            selectinload(Contest.organizer),
            selectinload(Contest.organization),
            selectinload(Contest.contest_problems).selectinload(ContestProblem.problem),
            selectinload(Contest.registrations),
        )
        .filter(Contest.id == contest_id)
        .first()
    )
    if contest is None:
        raise HTTPException(status_code=404, detail="Соревнование не найдено")
    return contest


def _to_contest_out(db: Session, contest: Contest, user: Optional[User], with_problems: bool) -> ContestOut:
    solved = solved_problem_ids(db, user.id if user else None, contest.id)
    problems: list[ContestProblemOut] = []
    if with_problems:
        links = sorted(contest.contest_problems, key=lambda item: item.order_index)
        for link in links:
            problems.append(
                ContestProblemOut(
                    problem_id=link.problem_id,
                    order_index=link.order_index,
                    code=problem_letter(link.order_index),
                    title=link.problem.title,
                    difficulty=link.problem.difficulty,
                    solved_by_me=link.problem_id in solved,
                )
            )
    return ContestOut(
        id=contest.id,
        title=contest.title,
        description=contest.description,
        problem_count=len(contest.contest_problems),
        participant_count=len({item.team_id for item in contest.registrations if item.team_id is not None})
        if contest.participation_format == "team"
        else len(contest.registrations),
        participation_format=contest.participation_format,
        start_time=isoformat_utc(contest.start_time),
        duration_minutes=contest.duration_minutes,
        phase=phase_of(contest),
        is_registered=is_registered(db, contest.id, user.id if user else None),
        is_owner=user is not None and (user.role == "admin" or contest.organizer_id == user.id),
        organizer_name=contest.organizer.username,
        organization_id=contest.organization_id,
        organization_name=contest.organization.name if contest.organization is not None else None,
        problems=problems,
    )


@router.get("", response_model=list[ContestOut])
def list_contests(
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> list[ContestOut]:
    contests = (
        db.query(Contest)
        .options(
            selectinload(Contest.organizer),
            selectinload(Contest.organization),
            selectinload(Contest.contest_problems),
            selectinload(Contest.registrations),
        )
        .all()
    )
    visible = [contest for contest in contests if visible_contest(contest, user)]
    # joinedload can duplicate rows
    unique = {contest.id: contest for contest in visible}
    items = list(unique.values())

    def sort_key(contest: Contest) -> tuple:
        phase = phase_of(contest)
        rank = {"running": 0, "upcoming": 1, "draft": 2, "finished": 3}[phase]
        stamp = contest.start_time.timestamp()
        if phase == "finished":
            stamp = -stamp
        return (rank, stamp)

    items.sort(key=sort_key)
    return [_to_contest_out(db, contest, user, False) for contest in items]


@router.post("", response_model=ContestOut)
def create_contest(
    payload: ContestIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_organizer),
) -> ContestOut:
    contest = Contest(
        title=payload.title.strip(),
        description=payload.description.strip(),
        start_time=as_naive_utc(payload.start_time),
        duration_minutes=payload.duration_minutes,
        status="draft",
        organizer_id=user.id,
        organization_id=_organization_for_user(db, user, payload.organization_id),
        participation_format=payload.participation_format,
    )
    db.add(contest)
    db.flush()
    _ensure_problem_selection(db, payload.problem_ids, contest.organization_id)
    replace_contest_problems(db, contest, payload.problem_ids)
    db.commit()
    db.expire_all()
    return _to_contest_out(db, _load_contest(db, contest.id), user, True)


@router.get("/{contest_id}", response_model=ContestOut)
def get_contest(
    contest_id: int,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> ContestOut:
    contest = _load_contest(db, contest_id)
    if not visible_contest(contest, user):
        raise HTTPException(status_code=404, detail="Соревнование не найдено")
    return _to_contest_out(db, contest, user, True)


@router.put("/{contest_id}", response_model=ContestOut)
def update_contest(
    contest_id: int,
    payload: ContestIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ContestOut:
    contest = _load_contest(db, contest_id)
    ensure_owner(user, contest)
    ensure_editable(contest)
    contest.title = payload.title.strip()
    contest.description = payload.description.strip()
    contest.start_time = as_naive_utc(payload.start_time)
    contest.duration_minutes = payload.duration_minutes
    if payload.participation_format != contest.participation_format and contest.registrations:
        raise HTTPException(status_code=400, detail="Нельзя сменить формат: уже есть зарегистрированные участники")
    contest.participation_format = payload.participation_format
    contest.organization_id = _organization_for_user(db, user, payload.organization_id)
    _ensure_problem_selection(db, payload.problem_ids, contest.organization_id)
    replace_contest_problems(db, contest, payload.problem_ids)
    db.commit()
    db.expire_all()
    return _to_contest_out(db, _load_contest(db, contest.id), user, True)


@router.post("/{contest_id}/publish", response_model=ContestOut)
def publish_contest(
    contest_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ContestOut:
    contest = _load_contest(db, contest_id)
    ensure_owner(user, contest)
    if contest.status == "published":
        raise HTTPException(status_code=400, detail="Соревнование уже опубликовано")
    if not contest.contest_problems:
        raise HTTPException(status_code=400, detail="Добавьте хотя бы одну задачу")
    contest.status = "published"
    db.commit()
    db.expire_all()
    return _to_contest_out(db, _load_contest(db, contest.id), user, True)


@router.post("/{contest_id}/finish", response_model=ContestOut)
def finish_contest(
    contest_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ContestOut:
    contest = _load_contest(db, contest_id)
    ensure_owner(user, contest)
    if phase_of(contest) != "running":
        raise HTTPException(status_code=400, detail="Досрочно завершить можно только идущее соревнование")
    contest.manually_finished = True
    db.commit()
    db.expire_all()
    return _to_contest_out(db, _load_contest(db, contest.id), user, True)


@router.post("/{contest_id}/register-team", response_model=ContestOut)
def register_team(
    contest_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ContestOut:
    contest = _load_contest(db, contest_id)
    if not visible_contest(contest, user) or contest.status != "published":
        raise HTTPException(status_code=404, detail="Соревнование не найдено")
    if contest.participation_format != "team":
        raise HTTPException(status_code=400, detail="Этот турнир индивидуальный")
    phase = phase_of(contest)
    if phase == "finished":
        raise HTTPException(status_code=400, detail="Регистрация закрыта: соревнование завершено")
    if phase == "draft":
        raise HTTPException(status_code=400, detail="Нельзя зарегистрироваться на черновик")
    membership = db.query(TeamMember).filter(TeamMember.user_id == user.id).first()
    if membership is None:
        raise HTTPException(status_code=400, detail="Сначала создайте команду или вступите в неё")
    team = db.get(Team, membership.team_id)
    if team is None or team.captain_id != user.id:
        raise HTTPException(status_code=403, detail="Команду записывает капитан")
    already = db.query(Registration).filter(Registration.contest_id == contest.id, Registration.team_id == team.id).first()
    if already:
        raise HTTPException(status_code=400, detail="Команда уже зарегистрирована")
    members = db.query(TeamMember, User).join(User, User.id == TeamMember.user_id).filter(TeamMember.team_id == team.id).all()
    for _member, account in members:
        taken = db.query(Registration).filter(Registration.contest_id == contest.id, Registration.user_id == account.id).first()
        if taken:
            raise HTTPException(status_code=400, detail=f"{account.username} уже участвует в этом турнире")
    for _member, account in members:
        db.add(Registration(contest_id=contest.id, user_id=account.id, team_id=team.id))
    db.commit()
    db.expire_all()
    return _to_contest_out(db, _load_contest(db, contest.id), user, True)


@router.post("/{contest_id}/register", response_model=ContestOut)
def register_for_contest(
    contest_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ContestOut:
    contest = _load_contest(db, contest_id)
    if not visible_contest(contest, user) or contest.status != "published":
        raise HTTPException(status_code=404, detail="Соревнование не найдено")
    phase = phase_of(contest)
    if phase == "finished":
        raise HTTPException(status_code=400, detail="Регистрация закрыта: соревнование завершено")
    if phase == "draft":
        raise HTTPException(status_code=400, detail="Нельзя зарегистрироваться на черновик")
    if contest.participation_format == "team":
        raise HTTPException(status_code=400, detail="На командный турнир регистрируется команда, а не отдельный участник")
    exists = (
        db.query(Registration)
        .filter(Registration.contest_id == contest.id, Registration.user_id == user.id)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Вы уже зарегистрированы")
    db.add(Registration(contest_id=contest.id, user_id=user.id))
    db.commit()
    db.expire_all()
    return _to_contest_out(db, _load_contest(db, contest.id), user, True)


@router.delete("/{contest_id}/register", response_model=ContestOut)
def unregister(
    contest_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ContestOut:
    contest = _load_contest(db, contest_id)
    if not visible_contest(contest, user):
        raise HTTPException(status_code=404, detail="Соревнование не найдено")
    if phase_of(contest) in ("running", "finished"):
        raise HTTPException(status_code=400, detail="Нельзя отменить регистрацию после старта")
    registration = (
        db.query(Registration)
        .filter(Registration.contest_id == contest.id, Registration.user_id == user.id)
        .first()
    )
    if registration is None:
        raise HTTPException(status_code=400, detail="Вы не зарегистрированы")
    if contest.participation_format == "team":
        team = db.get(Team, registration.team_id) if registration.team_id is not None else None
        if team is None or team.captain_id != user.id:
            raise HTTPException(status_code=403, detail="Регистрацию команды отменяет капитан")
        db.query(Registration).filter(Registration.contest_id == contest.id, Registration.team_id == team.id).delete(synchronize_session=False)
    else:
        db.delete(registration)
    db.commit()
    db.expire_all()
    return _to_contest_out(db, _load_contest(db, contest.id), user, True)


@router.get("/{contest_id}/standings", response_model=list[StandingOut])
def standings(
    contest_id: int,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> list[StandingOut]:
    contest = _load_contest(db, contest_id)
    if not visible_contest(contest, user):
        raise HTTPException(status_code=404, detail="Соревнование не найдено")
    return [StandingOut(**row) for row in build_standings(db, contest)]
