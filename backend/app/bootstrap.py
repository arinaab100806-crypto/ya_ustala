from __future__ import annotations

import os

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import User
from .security import hash_password


def ensure_admin(db: Session) -> None:
    """Создаёт первого администратора из окружения, если администраторов ещё нет."""
    if db.query(User).filter(User.role == "admin").first() is not None:
        return
    email = os.getenv("ADMIN_EMAIL", "").lower().strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    username = os.getenv("ADMIN_USERNAME", "admin").strip()
    if not email or len(password) < 6 or not username:
        return
    existing = db.query(User).filter(User.email == email).first()
    if existing is not None:
        existing.role = "admin"
        db.commit()
        return
    taken = db.query(User).filter(func.lower(User.username) == username.lower()).first()
    if taken is not None:
        return
    db.add(User(username=username, email=email, password_hash=hash_password(password), role="admin"))
    db.commit()
