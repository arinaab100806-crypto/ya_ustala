export type Role = "participant" | "organizer" | "admin";
export type Difficulty = "easy" | "medium" | "hard";
export type Language = "python" | "cpp" | "java" | "javascript";
export type Verdict = "OK" | "WA" | "TLE" | "RE" | "CE";
export type Phase = "draft" | "upcoming" | "running" | "finished";
export type ParticipationFormat = "individual" | "team";

export interface OrganizationMembership {
  organization_id: number;
  organization_name: string;
  member_role: "owner" | "organizer";
}

export interface User {
  id: number;
  username: string;
  email: string;
  role: Role;
  full_name?: string | null;
  birth_date?: string | null;
  can_organize: boolean;
  organizations: OrganizationMembership[];
}

export interface AdminOrganization {
  id: number;
  name: string;
  description: string;
  member_count: number;
  created_by_id: number | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Problem {
  id: number;
  title: string;
  short_description: string;
  difficulty: Difficulty;
  category: string;
  kind: "algorithmic" | "production";
  author_name: string;
  accepted_count: number;
  solved_by_me: boolean;
}

export interface Example {
  input: string;
  output: string;
}

export interface ProblemDetail extends Problem {
  statement: string;
  input_format: string;
  output_format: string;
  constraints: string;
  time_limit_ms: number;
  memory_limit_mb: number;
  examples: Example[];
}

export interface JudgeResult {
  verdict: Verdict;
  message: string | null;
  runtime_ms: number | null;
  tests_passed: number;
  tests_total: number;
  judge_mode: "unavailable" | "judge0";
  judge_label: string;
  samples_only: boolean;
  failed_input: string | null;
  failed_expected: string | null;
  failed_actual: string | null;
}

export interface Submission extends JudgeResult {
  id: number;
  problem_id: number;
  problem_title: string | null;
  contest_id: number | null;
  language: Language;
  source_code: string | null;
  created_at: string;
}

export interface ContestProblem {
  problem_id: number;
  order_index: number;
  code: string;
  title: string;
  difficulty: Difficulty;
  solved_by_me: boolean;
}

export interface Contest {
  id: number;
  title: string;
  description: string;
  problem_count: number;
  participant_count: number;
  participation_format: ParticipationFormat;
  start_time: string;
  duration_minutes: number;
  phase: Phase;
  is_registered: boolean;
  is_owner: boolean;
  organizer_name: string;
  organization_id: number | null;
  organization_name: string | null;
  problems: ContestProblem[];
}

export interface Standing {
  place: number;
  user_id: number;
  username: string;
  solved: number;
  time_seconds: number;
  team_id?: number | null;
}

export interface Dashboard {
  username: string;
  solved_count: number;
  submission_count: number;
  contests: Contest[];
  recent_submissions: Submission[];
}

export interface SystemInfo {
  judge_mode: "unavailable" | "judge0";
  judge_label: string;
  languages: Language[];
}

export interface ContestPayload {
  title: string;
  description: string;
  start_time: string;
  duration_minutes: number;
  participation_format: ParticipationFormat;
  organization_id: number | null;
  problem_ids: number[];
}

export interface OrganizationMine {
  id: number;
  name: string;
  description: string;
  logo_url: string | null;
  member_role: "owner" | "organizer";
}

export interface OrgProblem {
  id: number;
  title: string;
  short_description: string;
  difficulty: Difficulty;
  category: string;
  kind: "algorithmic" | "production";
  publication_status: "published" | "hidden";
  accepted_count: number;
}

export interface OrgTest {
  input_data: string;
  expected_output: string;
  is_sample: boolean;
}

export interface OrgProblemDetail extends OrgProblem {
  statement: string;
  input_format: string;
  output_format: string;
  constraints: string;
  time_limit_ms: number;
  memory_limit_mb: number;
  tests: OrgTest[];
}

export interface OrganizationCabinet extends OrganizationMine {
  problem_count: number;
  published_problem_count: number;
  contest_count: number;
  participant_count: number;
  members: Array<{ user_id: number; username: string; member_role: string }>;
  problems: OrgProblem[];
  contests: Array<{ id: number; title: string; phase: Phase; participation_format: ParticipationFormat }>;
}

export interface TeamCard {
  id: number;
  name: string;
  description: string;
  specialization: string;
  max_members: number;
  member_count: number;
  recruiting: boolean;
  captain_name: string;
}

export interface Team extends TeamCard {
  logo_url: string | null;
  captain_id: number;
  solved_count: number;
  contest_count: number;
  is_member: boolean;
  is_captain: boolean;
  members: Array<{ user_id: number; username: string; is_captain: boolean }>;
  applications: Array<{ id: number; user_id: number; username: string; status: string; created_at: string }>;
}

export interface FairPlayReport {
  id: number;
  problem_id: number;
  problem_title: string;
  username: string;
  matched_username: string;
  similarity_percent: number;
  status: "attention" | "reviewed";
  explanation: string;
  created_at: string;
}

export interface FairPlayParticipant {
  user_id: number;
  username: string;
  submission_count: number;
  solved_count: number;
  match_count: number;
  problem_titles: string[];
  matched_usernames: string[];
  max_similarity: number | null;
  status: "clear" | "attention" | "reviewed";
}

export interface FairPlayOverview {
  analyzed_at: string | null;
  participants: FairPlayParticipant[];
  reports: FairPlayReport[];
}

export interface FairPlayDetail extends FairPlayReport {
  submitted_at: string;
  matched_submitted_at: string;
  language: string;
  matched_language: string;
  source_code: string;
  matched_source_code: string;
  fragments: Array<{ start: number; end: number }>;
  matched_fragments: Array<{ start: number; end: number }>;
}

export interface ContestReport {
  id: number;
  report_format: "pdf" | "xlsx" | "csv";
  file_name: string;
  created_at: string;
  created_by: string;
}

export interface ProblemResult {
  id: number;
  username: string;
  verdict: Verdict;
  language: Language;
  tests_passed: number;
  tests_total: number;
  created_at: string;
}
