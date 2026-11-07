from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models import Organization, OrganizationMember, User
from ..schemas import RoleUpdateIn, UserOut
from .auth import user_out

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _admin: User = Depends(require_admin)) -> list[UserOut]:
    users = db.query(User).order_by(User.id.asc()).all()
    return [user_out(db, user) for user in users]


@router.patch("/users/{user_id}", response_model=UserOut)
def update_role(
    user_id: int,
    payload: RoleUpdateIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> UserOut:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if target.id == admin.id and payload.role != "admin":
        other_admins = db.query(func.count(User.id)).filter(User.role == "admin", User.id != admin.id).scalar() or 0
        if other_admins == 0:
            raise HTTPException(status_code=400, detail="Нельзя снять роль с единственного администратора")
    target.role = payload.role
    db.commit()
    db.refresh(target)
    return user_out(db, target)


@router.get("/organizations")
def list_organizations(db: Session = Depends(get_db), _admin: User = Depends(require_admin)) -> list[dict]:
    rows = db.query(Organization).order_by(Organization.id.asc()).all()
    result = []
    for organization in rows:
        members = db.query(func.count(OrganizationMember.id)).filter(OrganizationMember.organization_id == organization.id).scalar() or 0
        result.append(
            {
                "id": organization.id,
                "name": organization.name,
                "description": organization.description,
                "member_count": members,
                "created_by_id": organization.created_by_id,
            }
        )
    return result
