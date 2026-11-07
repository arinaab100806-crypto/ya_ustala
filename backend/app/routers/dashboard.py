from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_user
from ..models import Contest, Problem, Submission, User
from ..routers.contests import _to_contest_out
from ..routers.submissions import _to_submission_out
from ..schemas import DashboardOut
from ..services import phase_of

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DashboardOut:
    solved_count = (
        db.query(func.count(func.distinct(Submission.problem_id)))
        .filter(Submission.user_id == user.id, Submission.verdict == "OK")
        .scalar()
    ) or 0
    submission_count = db.query(func.count(Submission.id)).filter(Submission.user_id == user.id).scalar() or 0
    contests = (
        db.query(Contest)
        .options(
            selectinload(Contest.organizer),
            selectinload(Contest.contest_problems),
            selectinload(Contest.registrations),
        )
        .filter(Contest.status == "published")
        .all()
    )
    unique = {contest.id: contest for contest in contests}
    active = [contest for contest in unique.values() if phase_of(contest) in ("running", "upcoming")]
    active.sort(key=lambda contest: (0 if phase_of(contest) == "running" else 1, contest.start_time))
    recent_rows = (
        db.query(Submission, Problem.title)
        .join(Problem, Problem.id == Submission.problem_id)
        .filter(Submission.user_id == user.id)
        .order_by(Submission.created_at.desc())
        .limit(8)
        .all()
    )
    return DashboardOut(
        username=user.username,
        solved_count=solved_count,
        submission_count=submission_count,
        contests=[_to_contest_out(db, contest, user, False) for contest in active[:4]],
        recent_submissions=[_to_submission_out(submission, title) for submission, title in recent_rows],
    )
