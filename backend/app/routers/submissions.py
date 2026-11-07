from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from ..arena import ensure_match_submission, register_match_verdict
from ..database import get_db
from ..deps import get_current_user
from ..judge import JudgeServiceError, JudgeUnavailable, judge_code
from ..models import Contest, ContestProblem, OrganizationMember, Problem, Registration, Submission, User
from ..schemas import CodeIn, ResultOut, SubmissionOut
from ..services import isoformat_utc, phase_of

router = APIRouter(tags=["submissions"])


def _load_problem(db: Session, problem_id: int) -> Problem:
    problem = (
        db.query(Problem)
        .options(joinedload(Problem.tests))
        .filter(Problem.id == problem_id)
        .first()
    )
    if problem is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return problem


def _ensure_contest_submission(db: Session, user: User, problem: Problem, contest_id: Optional[int]) -> Optional[Contest]:
    if contest_id is None:
        return None
    contest = db.get(Contest, contest_id)
    if contest is None or (contest.status != "published" and contest.organizer_id != user.id):
        raise HTTPException(status_code=404, detail="Соревнование не найдено")
    linked = (
        db.query(ContestProblem)
        .filter(ContestProblem.contest_id == contest.id, ContestProblem.problem_id == problem.id)
        .first()
    )
    if linked is None:
        raise HTTPException(status_code=400, detail="Этой задачи нет в соревновании")
    registered = (
        db.query(Registration)
        .filter(Registration.contest_id == contest.id, Registration.user_id == user.id)
        .first()
    )
    if registered is None:
        raise HTTPException(status_code=403, detail="Сначала зарегистрируйтесь на соревнование")
    if phase_of(contest) != "running":
        raise HTTPException(status_code=403, detail="Отправлять решения можно только пока соревнование идёт")
    return contest


def _ensure_attempt(db: Session, user: User, problem: Problem, contest: Optional[Contest]) -> None:
    if problem.publication_status == "published" or contest is not None or user.role == "admin":
        return
    if problem.organization_id is not None:
        member = (
            db.query(OrganizationMember)
            .filter(
                OrganizationMember.organization_id == problem.organization_id,
                OrganizationMember.user_id == user.id,
                OrganizationMember.member_role.in_(("owner", "organizer")),
            )
            .first()
        )
        if member is not None:
            return
    raise HTTPException(status_code=404, detail="Задача не найдена")


def _result_from_outcome(outcome, samples_only: bool) -> ResultOut:
    return ResultOut(
        verdict=outcome.verdict,
        message=outcome.message,
        runtime_ms=outcome.runtime_ms,
        tests_passed=outcome.tests_passed,
        tests_total=outcome.tests_total,
        judge_mode=outcome.judge_mode,
        judge_label="Judge0" if outcome.judge_mode == "judge0" else "Проверка недоступна",
        samples_only=samples_only,
        failed_input=outcome.failed_input,
        failed_expected=outcome.failed_expected,
        failed_actual=outcome.failed_actual,
    )


def _to_submission_out(submission: Submission, title: Optional[str], include_code: bool = False) -> SubmissionOut:
    return SubmissionOut(
        id=submission.id,
        problem_id=submission.problem_id,
        problem_title=title,
        contest_id=submission.contest_id,
        language=submission.language,
        source_code=submission.source_code if include_code else None,
        created_at=isoformat_utc(submission.created_at),
        verdict=submission.verdict,
        message=submission.message,
        runtime_ms=submission.runtime_ms,
        tests_passed=submission.tests_passed,
        tests_total=submission.tests_total,
        judge_mode=submission.judge_mode,
        judge_label="Judge0" if submission.judge_mode == "judge0" else "Проверка недоступна",
    )


@router.post("/run", response_model=ResultOut)
def run_samples(payload: CodeIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ResultOut:
    if not payload.source_code.strip():
        raise HTTPException(status_code=400, detail="Код пустой")
    problem = _load_problem(db, payload.problem_id)
    contest = _ensure_contest_submission(db, user, problem, payload.contest_id)
    _ensure_attempt(db, user, problem, contest)
    try:
        outcome = judge_code(
            payload.source_code,
            payload.language,
            problem.tests,
            problem.time_limit_ms,
            problem.memory_limit_mb,
            samples_only=True,
        )
    except JudgeUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except JudgeServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _result_from_outcome(outcome, True)


@router.post("/submissions", response_model=SubmissionOut)
def create_submission(payload: CodeIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SubmissionOut:
    if not payload.source_code.strip():
        raise HTTPException(status_code=400, detail="Код пустой")
    problem = _load_problem(db, payload.problem_id)
    contest = None
    match = None
    if payload.match_id is not None and payload.contest_id is not None:
        raise HTTPException(status_code=400, detail="Решение относится либо к турниру, либо к матчу")
    if payload.match_id is not None:
        match = ensure_match_submission(db, user, problem, payload.match_id)
    else:
        contest = _ensure_contest_submission(db, user, problem, payload.contest_id)
        _ensure_attempt(db, user, problem, contest)
    try:
        outcome = judge_code(
            payload.source_code,
            payload.language,
            problem.tests,
            problem.time_limit_ms,
            problem.memory_limit_mb,
            samples_only=False,
        )
    except JudgeUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except JudgeServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    submission = Submission(
        user_id=user.id,
        problem_id=problem.id,
        contest_id=contest.id if contest else None,
        match_id=match.id if match else None,
        language=payload.language,
        source_code=payload.source_code,
        verdict=outcome.verdict,
        message=outcome.message,
        runtime_ms=outcome.runtime_ms,
        tests_passed=outcome.tests_passed,
        tests_total=outcome.tests_total,
        judge_mode=outcome.judge_mode,
    )
    db.add(submission)
    db.flush()
    if match is not None:
        register_match_verdict(db, match, user, problem, outcome.verdict)
    else:
        db.commit()
    db.refresh(submission)
    result = _to_submission_out(submission, problem.title)
    return result.model_copy(
        update={
            "failed_input": outcome.failed_input,
            "failed_expected": outcome.failed_expected,
            "failed_actual": outcome.failed_actual,
            "samples_only": False,
        }
    )


@router.get("/submissions", response_model=list[SubmissionOut])
def list_submissions(
    problem_id: Optional[int] = None,
    contest_id: Optional[int] = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SubmissionOut]:
    query = (
        db.query(Submission, Problem.title)
        .join(Problem, Problem.id == Submission.problem_id)
        .filter(Submission.user_id == user.id)
    )
    if problem_id is not None:
        query = query.filter(Submission.problem_id == problem_id)
    if contest_id is not None:
        query = query.filter(Submission.contest_id == contest_id)
    rows = query.order_by(Submission.created_at.desc()).limit(limit).all()
    return [_to_submission_out(submission, title) for submission, title in rows]


@router.get("/submissions/{submission_id}", response_model=SubmissionOut)
def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubmissionOut:
    row = (
        db.query(Submission, Problem.title)
        .join(Problem, Problem.id == Submission.problem_id)
        .filter(Submission.id == submission_id, Submission.user_id == user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Отправка не найдена")
    submission, title = row
    return _to_submission_out(submission, title, include_code=True)
