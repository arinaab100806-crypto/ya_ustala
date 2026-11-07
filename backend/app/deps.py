from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import OrganizationMember, User
from .security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def user_from_token(token: str, db: Session) -> Optional[User]:
    user_id = decode_access_token(token)
    if user_id is None:
        return None
    return db.get(User, user_id)


def can_organize(db: Session, user: User) -> bool:
    if user.role in ("organizer", "admin"):
        return True
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.user_id == user.id,
            OrganizationMember.member_role.in_(("owner", "organizer")),
        )
        .first()
    )
    return membership is not None


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    user = user_from_token(credentials.credentials, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Сессия истекла. Войдите снова")
    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if credentials is None:
        return None
    return user_from_token(credentials.credentials, db)


def require_organizer(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if not can_organize(db, user):
        raise HTTPException(status_code=403, detail="Доступно только организаторам")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Доступно только администратору")
    return user
