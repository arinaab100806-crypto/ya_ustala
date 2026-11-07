from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from ..contest_reports import report_file, write_report
from ..database import get_db
from ..deps import get_current_user
from ..models import Contest, ContestReport, User
from ..schemas import ContestReportOut, ReportCreateIn
from ..services import isoformat_utc, phase_of
from .fairplay import _can_review

router = APIRouter(prefix="/contests", tags=["reports"])

MEDIA = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
}


def _contest(db: Session, contest_id: int) -> Contest:
    contest = db.query(Contest).filter(Contest.id == contest_id).first()
    if contest is None:
        raise HTTPException(status_code=404, detail="Соревнование не найдено")
    return contest


def _ensure(db: Session, user: User, contest: Contest) -> None:
    if not _can_review(db, user, contest):
        raise HTTPException(status_code=403, detail="Отчёт доступен организатору этого турнира")


def _out(report: ContestReport) -> ContestReportOut:
    return ContestReportOut(
        id=report.id,
        report_format=report.report_format,
        file_name=report.file_name,
        created_at=isoformat_utc(report.created_at),
        created_by=report.created_by.username,
    )


@router.get("/{contest_id}/reports", response_model=list[ContestReportOut])
def list_reports(
    contest_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ContestReportOut]:
    contest = _contest(db, contest_id)
    _ensure(db, user, contest)
    reports = (
        db.query(ContestReport)
        .options(joinedload(ContestReport.created_by))
        .filter(ContestReport.contest_id == contest.id)
        .order_by(ContestReport.created_at.desc(), ContestReport.id.desc())
        .all()
    )
    return [_out(report) for report in reports]


@router.post("/{contest_id}/reports", response_model=ContestReportOut)
def create_report(
    contest_id: int,
    payload: ReportCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ContestReportOut:
    contest = _contest(db, contest_id)
    _ensure(db, user, contest)
    if phase_of(contest) != "finished":
        raise HTTPException(status_code=400, detail="Отчёт формируется после завершения турнира")
    file_name = write_report(db, contest, payload.report_format)
    report = ContestReport(
        contest_id=contest.id,
        report_format=payload.report_format,
        file_name=file_name,
        created_by_id=user.id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return _out(report)


@router.get("/{contest_id}/reports/{report_id}/download")
def download_report(
    contest_id: int,
    report_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    contest = _contest(db, contest_id)
    _ensure(db, user, contest)
    report = (
        db.query(ContestReport)
        .filter(ContestReport.id == report_id, ContestReport.contest_id == contest.id)
        .first()
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    path = report_file(report.file_name)
    return FileResponse(path, media_type=MEDIA.get(report.report_format, "application/octet-stream"), filename=report.file_name)
