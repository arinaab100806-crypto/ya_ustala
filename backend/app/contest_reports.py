from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import Contest, Registration, Team, User
from .services import build_standings, contest_end

REPORTS_DIR = Path(__file__).resolve().parents[1] / "data" / "reports"
_FONT_NAME = "CodeArenaReport"
_font_ready = False


def _stamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.strftime("%d.%m.%Y %H:%M UTC")


def _clock(seconds: int) -> str:
    hours, remainder = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _person(user: User) -> tuple[str, str]:
    return (user.full_name or "—", user.birth_date.isoformat() if user.birth_date else "—")


def _team_name(db: Session, team_id: Optional[int]) -> str:
    if team_id is None:
        return "—"
    team = db.get(Team, team_id)
    return team.name if team is not None else "—"


def build_document(db: Session, contest: Contest) -> tuple[list[str], list[str], list[list[str]], list[str], list[list[str]]]:
    standings = build_standings(db, contest)
    organizer = contest.organizer
    organizer_name = organizer.username
    if organizer.full_name:
        organizer_name = f"{organizer.full_name} ({organizer.username})"
    format_label = "Командный" if contest.participation_format == "team" else "Индивидуальный"
    organization = contest.organization.name if contest.organization is not None else "—"
    intro = [
        contest.title,
        contest.description or "—",
        f"Дата проведения: {_stamp(contest.start_time)} — {_stamp(contest_end(contest))}",
        "Турнир завершён досрочно." if contest.manually_finished else "Турнир завершён по расписанию.",
        f"Организатор: {organizer_name}",
        f"Организация: {organization}",
        f"Формат: {format_label}",
        "Балл равен числу решённых задач. При равенстве баллов выше результат с меньшим временем.",
        "Дисквалификации не зафиксированы.",
        f"Отчёт сформирован: {_stamp(datetime.utcnow())}",
        "Автоматически сформированный отчёт не является документом для присвоения спортивного разряда.",
    ]
    registrations = db.query(Registration).filter(Registration.contest_id == contest.id).all()
    if contest.participation_format == "team":
        headers = ["Место", "Команда", "Состав", "Решено", "Баллы", "Время"]
        rows: list[list[str]] = []
        place_by_team = {row.get("team_id"): row for row in standings}
        for row in standings:
            members = [item for item in registrations if item.team_id == row.get("team_id")]
            users = [item.user for item in members if item.user is not None]
            users.sort(key=lambda item: item.username.lower())
            roster = ", ".join(
                item.username if not item.full_name else f"{item.username} — {item.full_name}" for item in users
            ) or "—"
            rows.append(
                [
                    str(row["place"]),
                    row["username"],
                    roster,
                    str(row["solved"]),
                    str(row["solved"]),
                    _clock(row["time_seconds"]) if row["solved"] else "—",
                ]
            )
        member_headers = ["Участник", "ФИО", "Дата рождения", "Команда", "Место", "Результат"]
        member_rows: list[list[str]] = []
        for registration in sorted(registrations, key=lambda item: (item.team_id or 0, item.user.username.lower() if item.user else "")):
            if registration.user is None:
                continue
            standing = place_by_team.get(registration.team_id)
            full_name, birth = _person(registration.user)
            if standing is None:
                result = "0 баллов"
                place = "—"
            else:
                result = f"{standing['solved']} баллов"
                if standing["solved"]:
                    result = f"{result}, время {_clock(standing['time_seconds'])}"
                place = str(standing["place"])
            member_rows.append(
                [
                    registration.user.username,
                    full_name,
                    birth,
                    _team_name(db, registration.team_id),
                    place,
                    result,
                ]
            )
        return intro, headers, rows, member_headers, member_rows

    headers = ["Место", "Участник", "ФИО", "Дата рождения", "Команда", "Решено", "Баллы", "Время"]
    by_user = {row["user_id"]: row for row in standings}
    reg_by_user = {item.user_id: item for item in registrations}
    rows = []
    for standing in standings:
        registration = reg_by_user.get(standing["user_id"])
        person = registration.user if registration is not None and registration.user is not None else db.get(User, standing["user_id"])
        full_name, birth = _person(person) if person is not None else ("—", "—")
        team_id = registration.team_id if registration is not None else None
        rows.append(
            [
                str(standing["place"]),
                standing["username"],
                full_name,
                birth,
                _team_name(db, team_id),
                str(standing["solved"]),
                str(standing["solved"]),
                _clock(standing["time_seconds"]) if standing["solved"] else "—",
            ]
        )
    del by_user
    return intro, headers, rows, [], []


def write_report(db: Session, contest: Contest, report_format: str) -> str:
    intro, headers, rows, member_headers, member_rows = build_document(db, contest)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    ext = {"pdf": "pdf", "xlsx": "xlsx", "csv": "csv"}[report_format]
    file_name = f"{contest.id}-{stamp}.{ext}"
    suffix = 2
    while (REPORTS_DIR / file_name).exists():
        file_name = f"{contest.id}-{stamp}-{suffix}.{ext}"
        suffix += 1
    path = REPORTS_DIR / file_name
    if report_format == "csv":
        _write_csv(path, intro, headers, rows, member_headers, member_rows)
    elif report_format == "xlsx":
        _write_xlsx(path, intro, headers, rows, member_headers, member_rows)
    else:
        _write_pdf(path, intro, headers, rows, member_headers, member_rows)
    return file_name


def report_file(file_name: str) -> Path:
    if file_name != Path(file_name).name or not file_name:
        raise HTTPException(status_code=404, detail="Файл отчёта не найден")
    path = (REPORTS_DIR / file_name).resolve()
    if path.parent != REPORTS_DIR.resolve() or not path.is_file():
        raise HTTPException(status_code=404, detail="Файл отчёта не найден")
    return path


def _write_csv(
    path: Path,
    intro: list[str],
    headers: list[str],
    rows: list[list[str]],
    member_headers: list[str],
    member_rows: list[list[str]],
) -> None:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for line in intro:
        writer.writerow([line])
    writer.writerow([])
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    if member_headers:
        writer.writerow([])
        writer.writerow(["Участники"])
        writer.writerow(member_headers)
        for row in member_rows:
            writer.writerow(row)
    path.write_bytes(buffer.getvalue().encode("utf-8-sig"))


def _write_xlsx(
    path: Path,
    intro: list[str],
    headers: list[str],
    rows: list[list[str]],
    member_headers: list[str],
    member_rows: list[list[str]],
) -> None:
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.title = "Отчёт"
    for line in intro:
        sheet.append([line])
    sheet.append([])
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    if member_headers:
        sheet.append([])
        sheet.append(["Участники"])
        sheet.append(member_headers)
        for row in member_rows:
            sheet.append(row)
    book.save(path)


def _ensure_font() -> str:
    global _font_ready
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if _font_ready:
        return _FONT_NAME
    candidates = [
        os.getenv("REPORT_FONT", ""),
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            pdfmetrics.registerFont(TTFont(_FONT_NAME, candidate))
            _font_ready = True
            return _FONT_NAME
    raise HTTPException(status_code=500, detail="Для PDF не найден шрифт с кириллицей. Укажите REPORT_FONT.")


def _xml(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _write_pdf(
    path: Path,
    intro: list[str],
    headers: list[str],
    rows: list[list[str]],
    member_headers: list[str],
    member_rows: list[list[str]],
) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    font = _ensure_font()
    style = ParagraphStyle(name="ReportBody", fontName=font, fontSize=9, leading=12)
    small = ParagraphStyle(name="ReportCell", fontName=font, fontSize=8, leading=10)
    story = [Paragraph(_xml(line), style) for line in intro]
    story.append(Spacer(1, 12))

    def add_table(table_headers: list[str], table_rows: list[list[str]]) -> None:
        data = [[Paragraph(_xml(cell), small) for cell in table_headers]]
        for row in table_rows:
            data.append([Paragraph(_xml(cell), small) for cell in row])
        if len(data) == 1:
            data.append([Paragraph("—", small) for _cell in table_headers])
        table = Table(data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), font),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#312e81")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d4d4d8")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(table)

    add_table(headers, rows)
    if member_headers:
        story.append(Spacer(1, 14))
        story.append(Paragraph("Участники", style))
        story.append(Spacer(1, 6))
        add_table(member_headers, member_rows)
    document = SimpleDocTemplate(str(path), pagesize=landscape(A4), title=intro[0] if intro else "Отчёт")
    document.build(story)
