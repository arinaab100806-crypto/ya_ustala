from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..deps import get_current_user
from ..fairplay import analyze_contest, compare_sources
from ..models import Contest, FairPlayReport, OrganizationMember, Registration, Submission, User
from ..schemas import (
    FairPlayDetailOut,
    FairPlayFragmentOut,
    FairPlayOverviewOut,
    FairPlayParticipantOut,
    FairPlayReportOut,
)
from ..services import isoformat_utc

router = APIRouter(prefix="/contests", tags=["fairplay"])


def _contest(db: Session, contest_id: int) -> Contest:
    contest = db.query(Contest).filter(Contest.id == contest_id).first()
    if contest is None:
        raise HTTPException(status_code=404, detail="Соревнование не найдено")
    return contest


def _can_review(db: Session, user: User, contest: Contest) -> bool:
    if user.role == "admin" or contest.organizer_id == user.id:
        return True
    if contest.organization_id is None:
        return False
    member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == contest.organization_id,
            OrganizationMember.user_id == user.id,
            OrganizationMember.member_role.in_(("owner", "organizer")),
        )
        .first()
    )
    return member is not None


def _ensure_reviewer(db: Session, user: User, contest: Contest) -> None:
    if not _can_review(db, user, contest):
        raise HTTPException(status_code=403, detail="Проверка ответов доступна организатору этого турнира")


def _report(db: Session, contest_id: int, report_id: int) -> FairPlayReport:
    report = (
        db.query(FairPlayReport)
        .options(
            joinedload(FairPlayReport.submission).joinedload(Submission.user),
            joinedload(FairPlayReport.matched_submission).joinedload(Submission.user),
            joinedload(FairPlayReport.problem),
        )
        .filter(FairPlayReport.id == report_id, FairPlayReport.contest_id == contest_id)
        .first()
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    return report


def _overview(db: Session, contest: Contest) -> FairPlayOverviewOut:
    if contest.fairplay_analyzed_at is None:
        return FairPlayOverviewOut(analyzed_at=None, participants=[], reports=[])
    reports = (
        db.query(FairPlayReport)
        .options(
            joinedload(FairPlayReport.submission).joinedload(Submission.user),
            joinedload(FairPlayReport.matched_submission).joinedload(Submission.user),
            joinedload(FairPlayReport.problem),
        )
        .filter(FairPlayReport.contest_id == contest.id)
        .order_by(FairPlayReport.similarity_percent.desc(), FairPlayReport.id.asc())
        .all()
    )
    registrations = db.query(Registration).filter(Registration.contest_id == contest.id).all()
    submissions = db.query(Submission).filter(Submission.contest_id == contest.id).all()
    users: dict[int, User] = {}
    for row in registrations:
        if row.user is not None:
            users[row.user_id] = row.user
    for submission in submissions:
        users[submission.user_id] = submission.user
    participants: list[FairPlayParticipantOut] = []
    for user_id, person in users.items():
        own_submissions = [item for item in submissions if item.user_id == user_id]
        related = [
            item
            for item in reports
            if item.submission.user_id == user_id or item.matched_submission.user_id == user_id
        ]
        if not related:
            status = "clear"
        elif any(item.status != "reviewed" for item in related):
            status = "attention"
        else:
            status = "reviewed"
        titles: list[str] = []
        names: list[str] = []
        for item in related:
            if item.problem.title not in titles:
                titles.append(item.problem.title)
            other = item.matched_submission.user if item.submission.user_id == user_id else item.submission.user
            if other.username not in names:
                names.append(other.username)
        solved = {item.problem_id for item in own_submissions if item.verdict == "OK"}
        participants.append(
            FairPlayParticipantOut(
                user_id=user_id,
                username=person.username,
                submission_count=len(own_submissions),
                solved_count=len(solved),
                match_count=len(related),
                problem_titles=titles,
                matched_usernames=names,
                max_similarity=max(item.similarity_percent for item in related) if related else None,
                status=status,
            )
        )
    participants.sort(key=lambda item: (-item.match_count, item.username))
    return FairPlayOverviewOut(
        analyzed_at=isoformat_utc(contest.fairplay_analyzed_at),
        participants=participants,
        reports=[_report_out(item) for item in reports],
    )


def _report_out(report: FairPlayReport) -> FairPlayReportOut:
    return FairPlayReportOut(
        id=report.id,
        problem_id=report.problem_id,
        problem_title=report.problem.title,
        username=report.submission.user.username,
        matched_username=report.matched_submission.user.username,
        similarity_percent=report.similarity_percent,
        status=report.status,
        explanation=report.explanation,
        created_at=isoformat_utc(report.created_at),
    )


def _detail(report: FairPlayReport) -> FairPlayDetailOut:
    found = compare_sources(
        report.submission.source_code,
        report.submission.language,
        report.matched_submission.source_code,
        report.matched_submission.language,
    )
    fragments = found.fragments if found is not None else []
    matched = found.matched_fragments if found is not None else []
    return FairPlayDetailOut(
        id=report.id,
        problem_title=report.problem.title,
        username=report.submission.user.username,
        matched_username=report.matched_submission.user.username,
        similarity_percent=report.similarity_percent,
        status=report.status,
        explanation=report.explanation,
        submitted_at=isoformat_utc(report.submission.created_at),
        matched_submitted_at=isoformat_utc(report.matched_submission.created_at),
        language=report.submission.language,
        matched_language=report.matched_submission.language,
        source_code=report.submission.source_code,
        matched_source_code=report.matched_submission.source_code,
        fragments=[FairPlayFragmentOut(start=start, end=end) for start, end in fragments],
        matched_fragments=[FairPlayFragmentOut(start=start, end=end) for start, end in matched],
    )


@router.get("/{contest_id}/fairplay", response_model=FairPlayOverviewOut)
def fairplay_overview(
    contest_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FairPlayOverviewOut:
    contest = _contest(db, contest_id)
    _ensure_reviewer(db, user, contest)
    return _overview(db, contest)


@router.post("/{contest_id}/fairplay", response_model=FairPlayOverviewOut)
def fairplay_analyze(
    contest_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FairPlayOverviewOut:
    contest = _contest(db, contest_id)
    _ensure_reviewer(db, user, contest)
    analyze_contest(db, contest)
    db.expire_all()
    return _overview(db, _contest(db, contest_id))


@router.get("/{contest_id}/fairplay/reports/{report_id}", response_model=FairPlayDetailOut)
def fairplay_detail(
    contest_id: int,
    report_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FairPlayDetailOut:
    contest = _contest(db, contest_id)
    _ensure_reviewer(db, user, contest)
    return _detail(_report(db, contest_id, report_id))


@router.post("/{contest_id}/fairplay/reports/{report_id}/review", response_model=FairPlayDetailOut)
def fairplay_review(
    contest_id: int,
    report_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FairPlayDetailOut:
    contest = _contest(db, contest_id)
    _ensure_reviewer(db, user, contest)
    report = _report(db, contest_id, report_id)
    if report.status != "reviewed":
        report.status = "reviewed"
        report.reviewed_by_id = user.id
        report.reviewed_at = datetime.utcnow()
        db.commit()
        db.expire_all()
        report = _report(db, contest_id, report_id)
    return _detail(report)
