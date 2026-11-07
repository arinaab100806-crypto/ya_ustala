from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class MembershipOut(BaseModel):
    organization_id: int
    organization_name: str
    member_role: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    full_name: Optional[str] = None
    birth_date: Optional[date] = None
    can_organize: bool = False
    organizations: list[MembershipOut] = []
    model_config = ConfigDict(from_attributes=True)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class OrganizationRegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    organization_name: str = Field(min_length=2, max_length=160)
    organization_description: str = Field(default="", max_length=5000)


class RoleUpdateIn(BaseModel):
    role: Literal["participant", "organizer", "admin"]


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ExampleOut(BaseModel):
    input: str
    output: str


class ProblemOut(BaseModel):
    id: int
    title: str
    short_description: str
    difficulty: str
    category: str
    kind: str
    author_name: str
    accepted_count: int
    solved_by_me: bool = False


class ProblemDetail(ProblemOut):
    statement: str
    input_format: str
    output_format: str
    constraints: str
    time_limit_ms: int
    memory_limit_mb: int
    examples: list[ExampleOut]


class CodeIn(BaseModel):
    problem_id: int
    language: Literal["python", "cpp", "java", "javascript"]
    source_code: str = Field(min_length=1, max_length=100_000)
    contest_id: Optional[int] = None
    match_id: Optional[int] = None


class ResultOut(BaseModel):
    verdict: str
    message: Optional[str] = None
    runtime_ms: Optional[int] = None
    tests_passed: int = 0
    tests_total: int = 0
    judge_mode: str
    judge_label: str
    samples_only: bool = False
    failed_input: Optional[str] = None
    failed_expected: Optional[str] = None
    failed_actual: Optional[str] = None


class SubmissionOut(ResultOut):
    id: int
    problem_id: int
    problem_title: Optional[str] = None
    contest_id: Optional[int] = None
    language: str
    source_code: Optional[str] = None
    created_at: str


class ContestIn(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=1, max_length=5000)
    start_time: datetime
    duration_minutes: int = Field(ge=5, le=10080)
    problem_ids: list[int] = Field(min_length=1)
    participation_format: Literal["individual", "team"] = "individual"
    organization_id: Optional[int] = None


class ContestProblemOut(BaseModel):
    problem_id: int
    order_index: int
    code: str
    title: str
    difficulty: str
    solved_by_me: bool = False


class ContestOut(BaseModel):
    id: int
    title: str
    description: str
    problem_count: int
    participant_count: int
    participation_format: str
    start_time: str
    duration_minutes: int
    phase: str
    is_registered: bool
    is_owner: bool
    organizer_name: str
    organization_id: Optional[int] = None
    organization_name: Optional[str] = None
    problems: list[ContestProblemOut] = []


class StandingOut(BaseModel):
    place: int
    user_id: int
    username: str
    solved: int
    time_seconds: int
    team_id: Optional[int] = None


class DashboardOut(BaseModel):
    username: str
    solved_count: int
    submission_count: int
    contests: list[ContestOut]
    recent_submissions: list[SubmissionOut]


class SystemOut(BaseModel):
    judge_mode: str
    judge_label: str
    languages: list[str]


class TestIn(BaseModel):
    input_data: str = Field(max_length=20_000)
    expected_output: str = Field(max_length=20_000)
    is_sample: bool = False


class ProblemIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    short_description: str = Field(min_length=1, max_length=400)
    statement: str = Field(min_length=1, max_length=20_000)
    input_format: str = Field(min_length=1, max_length=4000)
    output_format: str = Field(min_length=1, max_length=4000)
    constraints: str = Field(min_length=1, max_length=4000)
    difficulty: Literal["easy", "medium", "hard"]
    category: str = Field(min_length=2, max_length=80)
    kind: Literal["algorithmic", "production"]
    time_limit_ms: int = Field(default=2000, ge=200, le=10000)
    memory_limit_mb: int = Field(default=256, ge=32, le=1024)
    tests: list[TestIn] = Field(min_length=1, max_length=40)


class OrganizationProfileIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=5000)
    logo_url: str = Field(default="", max_length=500)


class MemberIn(BaseModel):
    username: str = Field(min_length=3, max_length=32)


class OrgProblemOut(BaseModel):
    id: int
    title: str
    short_description: str
    difficulty: str
    category: str
    kind: str
    publication_status: str
    accepted_count: int


class OrgProblemDetail(OrgProblemOut):
    statement: str
    input_format: str
    output_format: str
    constraints: str
    time_limit_ms: int
    memory_limit_mb: int
    tests: list[TestIn]


class MemberOut(BaseModel):
    user_id: int
    username: str
    member_role: str


class OrgContestOut(BaseModel):
    id: int
    title: str
    phase: str
    participation_format: str


class OrganizationOut(BaseModel):
    id: int
    name: str
    description: str
    logo_url: Optional[str] = None
    member_role: str
    problem_count: int
    published_problem_count: int
    contest_count: int
    participant_count: int
    members: list[MemberOut]
    problems: list[OrgProblemOut]
    contests: list[OrgContestOut]


class OrganizationMineOut(BaseModel):
    id: int
    name: str
    description: str
    logo_url: Optional[str] = None
    member_role: str


class ProblemResultOut(BaseModel):
    id: int
    username: str
    verdict: str
    language: str
    tests_passed: int
    tests_total: int
    created_at: str


class TeamIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=5000)
    logo_url: str = Field(default="", max_length=500)
    specialization: str = Field(min_length=2, max_length=80)
    max_members: int = Field(default=3, ge=2, le=10)
    recruiting: bool = True


class TeamMemberOut(BaseModel):
    user_id: int
    username: str
    is_captain: bool


class TeamApplicationOut(BaseModel):
    id: int
    user_id: int
    username: str
    status: str
    created_at: str


class TeamOut(BaseModel):
    id: int
    name: str
    description: str
    logo_url: Optional[str] = None
    specialization: str
    max_members: int
    member_count: int
    recruiting: bool
    captain_id: int
    captain_name: str
    solved_count: int
    contest_count: int
    is_member: bool
    is_captain: bool
    members: list[TeamMemberOut] = []
    applications: list[TeamApplicationOut] = []


class TeamCardOut(BaseModel):
    id: int
    name: str
    description: str
    specialization: str
    max_members: int
    member_count: int
    recruiting: bool
    captain_name: str


class ProfileIn(BaseModel):
    full_name: str = Field(default="", max_length=160)
    birth_date: Optional[date] = None


class ReportCreateIn(BaseModel):
    report_format: Literal["pdf", "xlsx", "csv"]


class ContestReportOut(BaseModel):
    id: int
    report_format: str
    file_name: str
    created_at: str
    created_by: str


class FairPlayFragmentOut(BaseModel):
    start: int
    end: int


class FairPlayReportOut(BaseModel):
    id: int
    problem_id: int
    problem_title: str
    username: str
    matched_username: str
    similarity_percent: int
    status: str
    explanation: str
    created_at: str


class FairPlayParticipantOut(BaseModel):
    user_id: int
    username: str
    submission_count: int
    solved_count: int
    match_count: int
    problem_titles: list[str]
    matched_usernames: list[str]
    max_similarity: Optional[int] = None
    status: str


class FairPlayOverviewOut(BaseModel):
    analyzed_at: Optional[str] = None
    participants: list[FairPlayParticipantOut] = []
    reports: list[FairPlayReportOut] = []


class FairPlayDetailOut(BaseModel):
    id: int
    problem_title: str
    username: str
    matched_username: str
    similarity_percent: int
    status: str
    explanation: str
    submitted_at: str
    matched_submitted_at: str
    language: str
    matched_language: str
    source_code: str
    matched_source_code: str
    fragments: list[FairPlayFragmentOut]
    matched_fragments: list[FairPlayFragmentOut]
