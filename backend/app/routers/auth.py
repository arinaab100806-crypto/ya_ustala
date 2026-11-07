from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import can_organize, get_current_user
from ..models import Organization, OrganizationMember, User
from ..schemas import LoginIn, MembershipOut, OrganizationRegisterIn, ProfileIn, RegisterIn, TokenOut, UserOut
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def user_out(db: Session, user: User) -> UserOut:
    memberships = (
        db.query(OrganizationMember, Organization)
        .join(Organization, Organization.id == OrganizationMember.organization_id)
        .filter(OrganizationMember.user_id == user.id)
        .all()
    )
    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        full_name=user.full_name,
        birth_date=user.birth_date,
        can_organize=can_organize(db, user),
        organizations=[
            MembershipOut(organization_id=organization.id, organization_name=organization.name, member_role=membership.member_role)
            for membership, organization in memberships
        ],
    )


def _create_user(db: Session, username: str, email: str, password: str) -> User:
    if db.query(User).filter(func.lower(User.username) == username.lower()).first():
        raise HTTPException(status_code=400, detail="Пользователь с таким именем уже существует")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")
    user = User(username=username, email=email, password_hash=hash_password(password), role="participant")
    db.add(user)
    db.flush()
    return user


def _token(db: Session, user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id), user=user_out(db, user))


@router.post("/register", response_model=TokenOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> TokenOut:
    user = _create_user(db, payload.username.strip(), payload.email.lower().strip(), payload.password)
    db.commit()
    db.refresh(user)
    return _token(db, user)


@router.post("/register-organization", response_model=TokenOut)
def register_organization(payload: OrganizationRegisterIn, db: Session = Depends(get_db)) -> TokenOut:
    name = payload.organization_name.strip()
    folded = name.casefold()
    existing_names = [row[0] for row in db.query(Organization.name).all()]
    if any(current.casefold() == folded for current in existing_names):
        raise HTTPException(status_code=400, detail="Организация с таким названием уже есть")
    user = _create_user(db, payload.username.strip(), payload.email.lower().strip(), payload.password)
    organization = Organization(
        name=name,
        description=payload.organization_description.strip(),
        created_by_id=user.id,
    )
    db.add(organization)
    db.flush()
    db.add(OrganizationMember(organization_id=organization.id, user_id=user.id, member_role="owner"))
    db.commit()
    db.refresh(user)
    return _token(db, user)


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    return _token(db, user)


@router.get("/me", response_model=UserOut)
def me(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> UserOut:
    return user_out(db, user)


@router.patch("/profile", response_model=UserOut)
def update_profile(
    payload: ProfileIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserOut:
    full_name = payload.full_name.strip()
    if payload.birth_date is not None and (payload.birth_date > date.today() or payload.birth_date.year < 1900):
        raise HTTPException(status_code=400, detail="Проверьте дату рождения")
    user.full_name = full_name or None
    user.birth_date = payload.birth_date
    db.commit()
    db.refresh(user)
    return user_out(db, user)
