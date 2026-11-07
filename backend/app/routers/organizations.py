from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Contest, Organization, OrganizationMember, Problem, Registration, Submission, TestCase, User
from ..schemas import (
    MemberIn,
    OrgProblemDetail,
    OrgProblemOut,
    OrganizationMineOut,
    OrganizationOut,
    OrganizationProfileIn,
    ProblemIn,
    ProblemResultOut,
    TestIn,
)
from ..services import isoformat_utc, phase_of

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _staff(db: Session, user: User, organization_id: int) -> OrganizationMember:
    member = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == user.id)
        .first()
    )
    if member is None or member.member_role not in ("owner", "organizer"):
        raise HTTPException(status_code=403, detail="Недостаточно прав организации")
    return member


def _organization(db: Session, organization_id: int) -> Organization:
    organization = db.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Организация не найдена")
    return organization


def _name_taken(db: Session, name: str, except_id: int) -> bool:
    folded = name.casefold()
    rows = db.query(Organization.id, Organization.name).all()
    return any(row[0] != except_id and row[1].casefold() == folded for row in rows)


def _logo(value: str) -> Optional[str]:
    text = value.strip()
    if not text:
        return None
    if not (text.startswith("https://") or text.startswith("http://")):
        raise HTTPException(status_code=400, detail="Ссылка на логотип должна начинаться с http:// или https://")
    return text


def _replace_tests(db: Session, problem: Problem, tests: list[TestIn]) -> None:
    if not any(test.is_sample for test in tests):
        raise HTTPException(status_code=400, detail="Добавьте хотя бы один открытый пример")
    for test in list(problem.tests):
        db.delete(test)
    db.flush()
    for index, test in enumerate(tests):
        db.add(
            TestCase(
                problem_id=problem.id,
                input_data=test.input_data,
                expected_output=test.expected_output,
                is_sample=test.is_sample,
                order_index=index,
            )
        )
    db.flush()
    db.expire(problem, ["tests"])


def _apply_problem(problem: Problem, payload: ProblemIn) -> None:
    problem.title = payload.title.strip()
    problem.short_description = payload.short_description.strip()
    problem.statement = payload.statement.strip()
    problem.input_format = payload.input_format.strip()
    problem.output_format = payload.output_format.strip()
    problem.constraints = payload.constraints.strip()
    problem.difficulty = payload.difficulty
    problem.category = payload.category.strip()
    problem.kind = payload.kind
    problem.time_limit_ms = payload.time_limit_ms
    problem.memory_limit_mb = payload.memory_limit_mb


def _problem_out(problem: Problem, counts: dict[int, int]) -> OrgProblemOut:
    return OrgProblemOut(
        id=problem.id,
        title=problem.title,
        short_description=problem.short_description,
        difficulty=problem.difficulty,
        category=problem.category,
        kind=problem.kind,
        publication_status=problem.publication_status,
        accepted_count=counts.get(problem.id, 0),
    )


def _counts(db: Session) -> dict[int, int]:
    rows = (
        db.query(Submission.problem_id, func.count(Submission.id))
        .filter(Submission.verdict == "OK")
        .group_by(Submission.problem_id)
        .all()
    )
    return {problem_id: count for problem_id, count in rows}


def _cabinet(db: Session, organization: Organization, member: OrganizationMember) -> OrganizationOut:
    problems = (
        db.query(Problem)
        .filter(Problem.organization_id == organization.id)
        .order_by(Problem.id.asc())
        .all()
    )
    contests = (
        db.query(Contest)
        .filter(Contest.organization_id == organization.id)
        .order_by(Contest.id.desc())
        .all()
    )
    members = (
        db.query(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .filter(OrganizationMember.organization_id == organization.id)
        .order_by(OrganizationMember.id.asc())
        .all()
    )
    counts = _counts(db)
    registered = {
        row[0]
        for row in db.query(Registration.user_id)
        .join(Contest, Contest.id == Registration.contest_id)
        .filter(Contest.organization_id == organization.id)
        .all()
    }
    submitted = {
        row[0]
        for row in db.query(Submission.user_id)
        .join(Problem, Problem.id == Submission.problem_id)
        .filter(Problem.organization_id == organization.id)
        .all()
    }
    return OrganizationOut(
        id=organization.id,
        name=organization.name,
        description=organization.description,
        logo_url=organization.logo_url,
        member_role=member.member_role,
        problem_count=len(problems),
        published_problem_count=sum(1 for problem in problems if problem.publication_status == "published"),
        contest_count=len(contests),
        participant_count=len(registered | submitted),
        members=[{"user_id": user.id, "username": user.username, "member_role": membership.member_role} for membership, user in members],
        problems=[_problem_out(problem, counts) for problem in problems],
        contests=[
            {"id": contest.id, "title": contest.title, "phase": phase_of(contest), "participation_format": contest.participation_format}
            for contest in contests
        ],
    )


@router.get("/mine", response_model=list[OrganizationMineOut])
def my_organizations(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[OrganizationMineOut]:
    rows = (
        db.query(OrganizationMember, Organization)
        .join(Organization, Organization.id == OrganizationMember.organization_id)
        .filter(OrganizationMember.user_id == user.id, OrganizationMember.member_role.in_(("owner", "organizer")))
        .order_by(Organization.id.asc())
        .all()
    )
    return [
        OrganizationMineOut(
            id=organization.id,
            name=organization.name,
            description=organization.description,
            logo_url=organization.logo_url,
            member_role=member.member_role,
        )
        for member, organization in rows
    ]


@router.get("/{organization_id}", response_model=OrganizationOut)
def get_organization(
    organization_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrganizationOut:
    member = _staff(db, user, organization_id)
    return _cabinet(db, _organization(db, organization_id), member)


@router.patch("/{organization_id}", response_model=OrganizationOut)
def update_organization(
    organization_id: int,
    payload: OrganizationProfileIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrganizationOut:
    member = _staff(db, user, organization_id)
    organization = _organization(db, organization_id)
    name = payload.name.strip()
    if _name_taken(db, name, organization.id):
        raise HTTPException(status_code=400, detail="Организация с таким названием уже есть")
    organization.name = name
    organization.description = payload.description.strip()
    organization.logo_url = _logo(payload.logo_url)
    db.commit()
    db.refresh(organization)
    return _cabinet(db, organization, member)


@router.post("/{organization_id}/members", response_model=OrganizationOut)
def add_member(
    organization_id: int,
    payload: MemberIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrganizationOut:
    member = _staff(db, user, organization_id)
    if member.member_role != "owner":
        raise HTTPException(status_code=403, detail="Сотрудников добавляет владелец организации")
    account = db.query(User).filter(func.lower(User.username) == payload.username.strip().lower()).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    exists = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == account.id)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Пользователь уже в организации")
    db.add(OrganizationMember(organization_id=organization_id, user_id=account.id, member_role="organizer"))
    db.commit()
    return _cabinet(db, _organization(db, organization_id), member)


@router.delete("/{organization_id}/members/{member_user_id}", response_model=OrganizationOut)
def remove_member(
    organization_id: int,
    member_user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrganizationOut:
    member = _staff(db, user, organization_id)
    if member.member_role != "owner":
        raise HTTPException(status_code=403, detail="Состав меняет владелец организации")
    target = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == member_user_id)
        .first()
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    if target.member_role == "owner":
        raise HTTPException(status_code=400, detail="Нельзя удалить владельца организации")
    db.delete(target)
    db.commit()
    return _cabinet(db, _organization(db, organization_id), member)


@router.post("/{organization_id}/problems", response_model=OrgProblemDetail)
def create_problem(
    organization_id: int,
    payload: ProblemIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrgProblemDetail:
    _staff(db, user, organization_id)
    _organization(db, organization_id)
    problem = Problem(organization_id=organization_id, author_id=user.id, publication_status="hidden")
    _apply_problem(problem, payload)
    db.add(problem)
    db.flush()
    _replace_tests(db, problem, payload.tests)
    db.commit()
    db.refresh(problem)
    return _detail(problem)


@router.get("/{organization_id}/problems/{problem_id}", response_model=OrgProblemDetail)
def get_problem(
    organization_id: int,
    problem_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrgProblemDetail:
    _staff(db, user, organization_id)
    problem = _own_problem(db, organization_id, problem_id)
    return _detail(problem)


@router.put("/{organization_id}/problems/{problem_id}", response_model=OrgProblemDetail)
def update_problem(
    organization_id: int,
    problem_id: int,
    payload: ProblemIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrgProblemDetail:
    _staff(db, user, organization_id)
    problem = _own_problem(db, organization_id, problem_id)
    _apply_problem(problem, payload)
    _replace_tests(db, problem, payload.tests)
    db.commit()
    db.refresh(problem)
    return _detail(problem)


@router.post("/{organization_id}/problems/{problem_id}/publish", response_model=OrgProblemDetail)
def publish_problem(
    organization_id: int,
    problem_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrgProblemDetail:
    return _set_status(db, user, organization_id, problem_id, "published")


@router.post("/{organization_id}/problems/{problem_id}/hide", response_model=OrgProblemDetail)
def hide_problem(
    organization_id: int,
    problem_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrgProblemDetail:
    return _set_status(db, user, organization_id, problem_id, "hidden")


@router.get("/{organization_id}/problems/{problem_id}/results", response_model=list[ProblemResultOut])
def problem_results(
    organization_id: int,
    problem_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProblemResultOut]:
    _staff(db, user, organization_id)
    problem = _own_problem(db, organization_id, problem_id)
    rows = (
        db.query(Submission, User)
        .join(User, User.id == Submission.user_id)
        .filter(Submission.problem_id == problem.id)
        .order_by(Submission.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        ProblemResultOut(
            id=submission.id,
            username=account.username,
            verdict=submission.verdict,
            language=submission.language,
            tests_passed=submission.tests_passed,
            tests_total=submission.tests_total,
            created_at=isoformat_utc(submission.created_at),
        )
        for submission, account in rows
    ]


def _own_problem(db: Session, organization_id: int, problem_id: int) -> Problem:
    problem = (
        db.query(Problem)
        .filter(Problem.id == problem_id, Problem.organization_id == organization_id)
        .first()
    )
    if problem is None:
        raise HTTPException(status_code=404, detail="Задача организации не найдена")
    return problem


def _detail(problem: Problem) -> OrgProblemDetail:
    counts = {problem.id: 0}
    base = _problem_out(problem, counts)
    return OrgProblemDetail(
        **base.model_dump(),
        statement=problem.statement,
        input_format=problem.input_format,
        output_format=problem.output_format,
        constraints=problem.constraints,
        time_limit_ms=problem.time_limit_ms,
        memory_limit_mb=problem.memory_limit_mb,
        tests=[TestIn(input_data=test.input_data, expected_output=test.expected_output, is_sample=test.is_sample) for test in problem.tests],
    )


def _set_status(db: Session, user: User, organization_id: int, problem_id: int, status: str) -> OrgProblemDetail:
    _staff(db, user, organization_id)
    problem = _own_problem(db, organization_id, problem_id)
    problem.publication_status = status
    db.commit()
    db.refresh(problem)
    return _detail(problem)
