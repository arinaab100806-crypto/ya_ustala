from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, get_optional_user
from ..models import Registration, Submission, Team, TeamApplication, TeamMember, User
from ..schemas import TeamApplicationOut, TeamCardOut, TeamIn, TeamMemberOut, TeamOut
from ..services import isoformat_utc

router = APIRouter(prefix="/teams", tags=["teams"])


def _logo(value: str) -> Optional[str]:
    text = value.strip()
    if not text:
        return None
    if not (text.startswith("https://") or text.startswith("http://")):
        raise HTTPException(status_code=400, detail="Ссылка на логотип должна начинаться с http:// или https://")
    return text


def _name_taken(db: Session, name: str, except_id: Optional[int] = None) -> bool:
    folded = name.casefold()
    rows = db.query(Team.id, Team.name).all()
    return any(row[0] != except_id and row[1].casefold() == folded for row in rows)


def _membership(db: Session, user_id: int) -> Optional[TeamMember]:
    return db.query(TeamMember).filter(TeamMember.user_id == user_id).first()


def _team(db: Session, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Команда не найдена")
    return team


def _members(db: Session, team_id: int) -> list[tuple[TeamMember, User]]:
    return (
        db.query(TeamMember, User)
        .join(User, User.id == TeamMember.user_id)
        .filter(TeamMember.team_id == team_id)
        .order_by(TeamMember.joined_at.asc())
        .all()
    )


def _to_out(db: Session, team: Team, user: Optional[User]) -> TeamOut:
    members = _members(db, team.id)
    user_ids = [account.id for _member, account in members]
    solved_ids = {
        row[0]
        for row in db.query(Submission.problem_id)
        .filter(Submission.user_id.in_(user_ids), Submission.verdict == "OK")
        .distinct()
        .all()
    } if user_ids else set()
    contest_ids = {
        row[0]
        for row in db.query(Registration.contest_id).filter(Registration.team_id == team.id).distinct().all()
    }
    is_captain = user is not None and team.captain_id == user.id
    applications: list[TeamApplicationOut] = []
    if is_captain:
        pending = (
            db.query(TeamApplication, User)
            .join(User, User.id == TeamApplication.user_id)
            .filter(TeamApplication.team_id == team.id, TeamApplication.status == "pending")
            .order_by(TeamApplication.created_at.asc())
            .all()
        )
        applications = [
            TeamApplicationOut(
                id=application.id,
                user_id=account.id,
                username=account.username,
                status=application.status,
                created_at=isoformat_utc(application.created_at),
            )
            for application, account in pending
        ]
    return TeamOut(
        id=team.id,
        name=team.name,
        description=team.description,
        logo_url=team.logo_url,
        specialization=team.specialization,
        max_members=team.max_members,
        member_count=len(members),
        recruiting=team.recruiting,
        captain_id=team.captain_id,
        captain_name=team.captain.username,
        solved_count=len(solved_ids),
        contest_count=len(contest_ids),
        is_member=user is not None and user.id in user_ids,
        is_captain=is_captain,
        members=[TeamMemberOut(user_id=account.id, username=account.username, is_captain=account.id == team.captain_id) for _member, account in members],
        applications=applications,
    )


@router.get("/mine", response_model=Optional[TeamOut])
def my_team(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Optional[TeamOut]:
    membership = _membership(db, user.id)
    if membership is None:
        return None
    team = _team(db, membership.team_id)
    return _to_out(db, team, user)


@router.get("", response_model=list[TeamCardOut])
def list_teams(
    search: str = "",
    specialization: str = "",
    recruiting: str = "",
    db: Session = Depends(get_db),
) -> list[TeamCardOut]:
    teams = db.query(Team).order_by(Team.name.asc()).all()
    needle = search.strip().casefold()
    specialty = specialization.strip().casefold()
    if needle:
        teams = [team for team in teams if needle in team.name.casefold() or needle in team.description.casefold()]
    if specialty:
        teams = [team for team in teams if specialty in team.specialization.casefold()]
    if recruiting == "open":
        teams = [team for team in teams if team.recruiting]
    elif recruiting == "closed":
        teams = [team for team in teams if not team.recruiting]
    elif recruiting:
        raise HTTPException(status_code=400, detail="Неизвестный фильтр набора")
    cards = []
    for team in teams:
        count = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()
        cards.append(
            TeamCardOut(
                id=team.id,
                name=team.name,
                description=team.description,
                specialization=team.specialization,
                max_members=team.max_members,
                member_count=count,
                recruiting=team.recruiting,
                captain_name=team.captain.username,
            )
        )
    return cards


@router.post("", response_model=TeamOut)
def create_team(payload: TeamIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> TeamOut:
    if _membership(db, user.id) is not None:
        raise HTTPException(status_code=400, detail="Вы уже состоите в команде")
    name = payload.name.strip()
    if _name_taken(db, name):
        raise HTTPException(status_code=400, detail="Команда с таким названием уже есть")
    team = Team(
        name=name,
        description=payload.description.strip(),
        logo_url=_logo(payload.logo_url),
        specialization=payload.specialization.strip(),
        max_members=payload.max_members,
        recruiting=payload.recruiting,
        captain_id=user.id,
    )
    db.add(team)
    db.flush()
    db.add(TeamMember(team_id=team.id, user_id=user.id))
    db.commit()
    db.refresh(team)
    return _to_out(db, team, user)


@router.get("/{team_id}", response_model=TeamOut)
def get_team(
    team_id: int,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> TeamOut:
    return _to_out(db, _team(db, team_id), user)


@router.patch("/{team_id}", response_model=TeamOut)
def update_team(
    team_id: int,
    payload: TeamIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TeamOut:
    team = _team(db, team_id)
    if team.captain_id != user.id:
        raise HTTPException(status_code=403, detail="Информацию команды меняет капитан")
    name = payload.name.strip()
    if _name_taken(db, name, team.id):
        raise HTTPException(status_code=400, detail="Команда с таким названием уже есть")
    member_count = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()
    if payload.max_members < member_count:
        raise HTTPException(status_code=400, detail="Размер команды меньше текущего состава")
    team.name = name
    team.description = payload.description.strip()
    team.logo_url = _logo(payload.logo_url)
    team.specialization = payload.specialization.strip()
    team.max_members = payload.max_members
    team.recruiting = payload.recruiting
    db.commit()
    db.refresh(team)
    return _to_out(db, team, user)


@router.post("/{team_id}/applications", response_model=TeamOut)
def apply_to_team(
    team_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TeamOut:
    team = _team(db, team_id)
    if _membership(db, user.id) is not None:
        raise HTTPException(status_code=400, detail="Нельзя состоять в нескольких командах")
    if not team.recruiting:
        raise HTTPException(status_code=400, detail="Набор в команду закрыт")
    member_count = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()
    if member_count >= team.max_members:
        raise HTTPException(status_code=400, detail="В команде больше нет мест")
    existing = (
        db.query(TeamApplication)
        .filter(TeamApplication.team_id == team.id, TeamApplication.user_id == user.id)
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=400, detail="Повторную заявку отправить нельзя")
    db.add(TeamApplication(team_id=team.id, user_id=user.id, status="pending"))
    db.commit()
    return _to_out(db, team, user)


@router.post("/{team_id}/applications/{application_id}/accept", response_model=TeamOut)
def accept_application(
    team_id: int,
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TeamOut:
    team = _team(db, team_id)
    if team.captain_id != user.id:
        raise HTTPException(status_code=403, detail="Заявки принимает капитан")
    application = db.get(TeamApplication, application_id)
    if application is None or application.team_id != team.id or application.status != "pending":
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if _membership(db, application.user_id) is not None:
        raise HTTPException(status_code=400, detail="Пользователь уже состоит в команде")
    member_count = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()
    if member_count >= team.max_members:
        raise HTTPException(status_code=400, detail="В команде больше нет мест")
    application.status = "accepted"
    db.add(TeamMember(team_id=team.id, user_id=application.user_id))
    others = (
        db.query(TeamApplication)
        .filter(TeamApplication.user_id == application.user_id, TeamApplication.status == "pending", TeamApplication.id != application.id)
        .all()
    )
    for other in others:
        other.status = "rejected"
    db.commit()
    return _to_out(db, team, user)


@router.post("/{team_id}/applications/{application_id}/reject", response_model=TeamOut)
def reject_application(
    team_id: int,
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TeamOut:
    team = _team(db, team_id)
    if team.captain_id != user.id:
        raise HTTPException(status_code=403, detail="Заявки рассматривает капитан")
    application = db.get(TeamApplication, application_id)
    if application is None or application.team_id != team.id or application.status != "pending":
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    application.status = "rejected"
    db.commit()
    return _to_out(db, team, user)


@router.delete("/{team_id}/members/{member_user_id}", response_model=TeamOut)
def remove_member(
    team_id: int,
    member_user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TeamOut:
    team = _team(db, team_id)
    if team.captain_id != user.id:
        raise HTTPException(status_code=403, detail="Состав меняет капитан")
    if member_user_id == team.captain_id:
        raise HTTPException(status_code=400, detail="Капитана нельзя исключить")
    membership = (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team.id, TeamMember.user_id == member_user_id)
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Участник не найден")
    db.delete(membership)
    db.commit()
    return _to_out(db, team, user)


@router.delete("/mine", response_model=Optional[TeamOut])
def leave_team(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Optional[TeamOut]:
    membership = _membership(db, user.id)
    if membership is None:
        raise HTTPException(status_code=400, detail="Вы не состоите в команде")
    team = _team(db, membership.team_id)
    if team.captain_id == user.id:
        raise HTTPException(status_code=400, detail="Капитан не может покинуть команду")
    db.delete(membership)
    db.commit()
    return None
