from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "Users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="participant")
    full_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    submissions: Mapped[list["Submission"]] = relationship(back_populates="user")
    registrations: Mapped[list["Registration"]] = relationship(back_populates="user")
    contests: Mapped[list["Contest"]] = relationship(back_populates="organizer")
    organization_memberships: Mapped[list["OrganizationMember"]] = relationship(back_populates="user")
    captained_teams: Mapped[list["Team"]] = relationship(back_populates="captain")


class Problem(Base):
    __tablename__ = "Problems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    short_description: Mapped[str] = mapped_column(String(400))
    statement: Mapped[str] = mapped_column(Text)
    input_format: Mapped[str] = mapped_column(Text)
    output_format: Mapped[str] = mapped_column(Text)
    constraints: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(20), index=True)
    category: Mapped[str] = mapped_column(String(80), default="общее", index=True)
    kind: Mapped[str] = mapped_column(String(20), default="algorithmic", index=True)
    publication_status: Mapped[str] = mapped_column(String(20), default="published", index=True)
    organization_id: Mapped[Optional[int]] = mapped_column(ForeignKey("Organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    author_id: Mapped[Optional[int]] = mapped_column(ForeignKey("Users.id", ondelete="SET NULL"), nullable=True, index=True)
    time_limit_ms: Mapped[int] = mapped_column(Integer, default=2000)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, default=256)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped[Optional["Organization"]] = relationship(back_populates="problems")
    author: Mapped[Optional[User]] = relationship()
    tests: Mapped[list["TestCase"]] = relationship(
        back_populates="problem",
        cascade="all, delete-orphan",
        order_by="TestCase.order_index",
    )


class TestCase(Base):
    __tablename__ = "TestCases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("Problems.id", ondelete="CASCADE"), index=True)
    input_data: Mapped[str] = mapped_column(Text)
    expected_output: Mapped[str] = mapped_column(Text)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    problem: Mapped[Problem] = relationship(back_populates="tests")


class Contest(Base):
    __tablename__ = "Contests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    start_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    participation_format: Mapped[str] = mapped_column(String(20), default="individual", index=True)
    organizer_id: Mapped[int] = mapped_column(ForeignKey("Users.id"), index=True)
    organization_id: Mapped[Optional[int]] = mapped_column(ForeignKey("Organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    manually_finished: Mapped[bool] = mapped_column(Boolean, default=False)
    fairplay_analyzed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organizer: Mapped[User] = relationship(back_populates="contests")
    organization: Mapped[Optional["Organization"]] = relationship(back_populates="contests")
    contest_problems: Mapped[list["ContestProblem"]] = relationship(
        back_populates="contest",
        cascade="all, delete-orphan",
        order_by="ContestProblem.order_index",
    )
    registrations: Mapped[list["Registration"]] = relationship(
        back_populates="contest",
        cascade="all, delete-orphan",
    )


class ContestProblem(Base):
    __tablename__ = "ContestProblems"
    __table_args__ = (UniqueConstraint("contest_id", "problem_id", name="uq_contest_problem"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("Contests.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("Problems.id"), index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    contest: Mapped[Contest] = relationship(back_populates="contest_problems")
    problem: Mapped[Problem] = relationship()


class Registration(Base):
    __tablename__ = "Registrations"
    __table_args__ = (UniqueConstraint("contest_id", "user_id", name="uq_registration"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("Contests.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("Users.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("Teams.id", ondelete="SET NULL"), nullable=True, index=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    contest: Mapped[Contest] = relationship(back_populates="registrations")
    user: Mapped[User] = relationship(back_populates="registrations")
    team: Mapped[Optional["Team"]] = relationship()


class Submission(Base):
    __tablename__ = "Submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("Users.id"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("Problems.id"), index=True)
    contest_id: Mapped[Optional[int]] = mapped_column(ForeignKey("Contests.id"), nullable=True, index=True)
    match_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ArenaMatches.id"), nullable=True, index=True)
    language: Mapped[str] = mapped_column(String(32))
    source_code: Mapped[str] = mapped_column(Text)
    verdict: Mapped[str] = mapped_column(String(8), index=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    runtime_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tests_passed: Mapped[int] = mapped_column(Integer, default=0)
    tests_total: Mapped[int] = mapped_column(Integer, default=0)
    judge_mode: Mapped[str] = mapped_column(String(16), default="demo")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user: Mapped[User] = relationship(back_populates="submissions")
    problem: Mapped[Problem] = relationship()
    contest: Mapped[Optional[Contest]] = relationship()


class Organization(Base):
    __tablename__ = "Organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("Users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    created_by: Mapped[User] = relationship()
    members: Mapped[list["OrganizationMember"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    problems: Mapped[list[Problem]] = relationship(back_populates="organization")
    contests: Mapped[list[Contest]] = relationship(back_populates="organization")


class OrganizationMember(Base):
    __tablename__ = "OrganizationMembers"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_organization_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("Organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("Users.id", ondelete="CASCADE"), index=True)
    member_role: Mapped[str] = mapped_column(String(20), default="organizer")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped[Organization] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="organization_memberships")


class Team(Base):
    __tablename__ = "Teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    specialization: Mapped[str] = mapped_column(String(80), default="", index=True)
    max_members: Mapped[int] = mapped_column(Integer, default=3)
    recruiting: Mapped[bool] = mapped_column(Boolean, default=True)
    captain_id: Mapped[int] = mapped_column(ForeignKey("Users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    captain: Mapped[User] = relationship(back_populates="captained_teams")
    members: Mapped[list["TeamMember"]] = relationship(back_populates="team", cascade="all, delete-orphan")
    applications: Mapped[list["TeamApplication"]] = relationship(back_populates="team", cascade="all, delete-orphan")


class TeamMember(Base):
    __tablename__ = "TeamMembers"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("Teams.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("Users.id", ondelete="CASCADE"), unique=True, index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    team: Mapped[Team] = relationship(back_populates="members")
    user: Mapped[User] = relationship()


class TeamApplication(Base):
    __tablename__ = "TeamApplications"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_application"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("Teams.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("Users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    team: Mapped[Team] = relationship(back_populates="applications")
    user: Mapped[User] = relationship()


class FairPlayReport(Base):
    __tablename__ = "FairPlayReports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("Contests.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("Problems.id"), index=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("Submissions.id", ondelete="CASCADE"), index=True)
    matched_submission_id: Mapped[int] = mapped_column(ForeignKey("Submissions.id", ondelete="CASCADE"), index=True)
    similarity_percent: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="attention", index=True)
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("Users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    contest: Mapped[Contest] = relationship()
    problem: Mapped[Problem] = relationship()
    submission: Mapped[Submission] = relationship(foreign_keys=[submission_id])
    matched_submission: Mapped[Submission] = relationship(foreign_keys=[matched_submission_id])


class ContestReport(Base):
    __tablename__ = "ContestReports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("Contests.id", ondelete="CASCADE"), index=True)
    report_format: Mapped[str] = mapped_column(String(8))
    file_name: Mapped[str] = mapped_column(String(255))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("Users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    contest: Mapped[Contest] = relationship()
    created_by: Mapped[User] = relationship()


class ArenaMatch(Base):
    __tablename__ = "ArenaMatches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mode: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16), default="waiting", index=True)
    organizer_id: Mapped[int] = mapped_column(ForeignKey("Users.id"), index=True)
    invite_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    winner_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    organizer: Mapped[User] = relationship()
    seats: Mapped[list["ArenaSeat"]] = relationship(back_populates="match", cascade="all, delete-orphan")
    tasks: Mapped[list["ArenaTask"]] = relationship(back_populates="match", cascade="all, delete-orphan")


class ArenaSeat(Base):
    __tablename__ = "ArenaSeats"
    __table_args__ = (
        UniqueConstraint("match_id", "slot", name="uq_arena_seat_slot"),
        UniqueConstraint("match_id", "user_id", name="uq_arena_seat_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("ArenaMatches.id", ondelete="CASCADE"), index=True)
    slot: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("Users.id"), nullable=True, index=True)

    match: Mapped[ArenaMatch] = relationship(back_populates="seats")
    user: Mapped[Optional[User]] = relationship()


class ArenaTask(Base):
    __tablename__ = "ArenaTasks"
    __table_args__ = (UniqueConstraint("match_id", "problem_id", name="uq_arena_task"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("ArenaMatches.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("Problems.id"), index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    assignee_role: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    match: Mapped[ArenaMatch] = relationship(back_populates="tasks")
    problem: Mapped[Problem] = relationship()


class ArenaPresence(Base):
    __tablename__ = "ArenaPresence"
    __table_args__ = (UniqueConstraint("match_id", "user_id", name="uq_arena_presence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("ArenaMatches.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("Users.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[Optional[int]] = mapped_column(ForeignKey("Problems.id"), nullable=True)
    stage: Mapped[str] = mapped_column(String(16), default="coding")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ArenaQueue(Base):
    __tablename__ = "ArenaQueue"

    user_id: Mapped[int] = mapped_column(ForeignKey("Users.id", ondelete="CASCADE"), primary_key=True)
    mode: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
