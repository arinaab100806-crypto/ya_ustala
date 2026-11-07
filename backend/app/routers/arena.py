from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..arena import active_match, create_match, enqueue, join_match, leave_queue, serialize_match, set_presence
from ..database import get_db
from ..deps import get_current_user
from ..models import User

router = APIRouter(prefix="/matches", tags=["matches"])


class QueueIn(BaseModel):
    mode: str = Field(pattern=r"^(duel|team)$")


class MatchTaskIn(BaseModel):
    problem_id: int
    assignee_role: Optional[int] = None


class MatchCreateIn(BaseModel):
    mode: str = Field(pattern=r"^(duel|team)$")
    tasks: list[MatchTaskIn] = Field(min_length=1, max_length=8)


class PresenceIn(BaseModel):
    problem_id: int
    stage: str = Field(pattern=r"^(coding|fixing)$")


@router.get("/current")
def current_match(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    match = active_match(db, user.id)
    if match is None:
        return {"match": None}
    return {"match": serialize_match(db, match, user)}


@router.post("/queue")
def join_queue(payload: QueueIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return enqueue(db, user, payload.mode)


@router.delete("/queue")
def exit_queue(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    leave_queue(db, user)
    return {"ok": True}


@router.post("")
def open_match(payload: MatchCreateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    roles = [task.assignee_role for task in payload.tasks]
    match = create_match(db, user, payload.mode, [task.problem_id for task in payload.tasks], roles if payload.mode == "team" else None)
    return serialize_match(db, match, user)


@router.post("/join/{invite_code}")
def accept_invite(invite_code: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    match = join_match(db, user, invite_code)
    return serialize_match(db, match, user)


@router.get("/{match_id}")
def get_match(match_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    from ..arena import _load

    match = _load(db, match_id)
    if not any(seat.user_id == user.id for seat in match.seats) and match.organizer_id != user.id:
        raise HTTPException(status_code=403, detail="Этот матч вам недоступен")
    return serialize_match(db, match, user)


@router.post("/{match_id}/presence")
def update_presence(
    match_id: int,
    payload: PresenceIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    match = set_presence(db, user, match_id, payload.problem_id, payload.stage)
    return serialize_match(db, match, user)
