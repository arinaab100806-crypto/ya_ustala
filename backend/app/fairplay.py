from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from .models import Contest, FairPlayReport, Registration, Submission

KEYWORDS = {
    "and", "as", "assert", "async", "await", "break", "class", "continue", "def", "del",
    "elif", "else", "except", "finally", "for", "from", "global", "if", "import", "in",
    "is", "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try", "while",
    "with", "yield", "true", "false", "none", "self",
    "int", "str", "float", "bool", "list", "dict", "set", "tuple", "map", "sum", "max",
    "min", "len", "range", "input", "print", "split", "strip", "append", "sort", "sorted",
    "public", "private", "protected", "static", "void", "new", "this", "extends",
    "implements", "interface", "package", "throws", "throw", "catch", "system", "out",
    "println", "string", "scanner", "main",
    "include", "using", "namespace", "std", "cin", "cout", "endl", "vector", "iostream",
    "const", "auto", "template", "typename", "struct", "enum",
    "function", "var", "let", "const", "console", "log", "document", "return",
    "null", "undefined", "of",
}


@dataclass
class CodeMatch:
    percent: int
    explanation: str
    fragments: list[tuple[int, int]]
    matched_fragments: list[tuple[int, int]]


def _scan(source: str, language: str) -> list[tuple[str, int, int]]:
    tokens: list[tuple[str, int, int]] = []
    i = 0
    n = len(source)
    c_like = language != "python"
    while i < n:
        ch = source[i]
        if ch.isspace():
            i += 1
            continue
        if language == "python" and ch == "#":
            while i < n and source[i] != "\n":
                i += 1
            continue
        if c_like and source.startswith("//", i):
            while i < n and source[i] != "\n":
                i += 1
            continue
        if c_like and source.startswith("/*", i):
            end = source.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        if ch in ("'", '"'):
            start = i
            quote = ch
            triple = language == "python" and source.startswith(quote * 3, i)
            if triple:
                end = source.find(quote * 3, i + 3)
                i = n if end < 0 else end + 3
            else:
                i += 1
                while i < n:
                    if source[i] == "\\":
                        i += 2
                        continue
                    if source[i] == quote or source[i] == "\n":
                        i += 1
                        break
                    i += 1
            tokens.append((source[start:i], start, i))
            continue
        if ch.isalpha() or ch == "_":
            start = i
            i += 1
            while i < n and (source[i].isalnum() or source[i] == "_"):
                i += 1
            tokens.append((source[start:i], start, i))
            continue
        if ch.isdigit():
            start = i
            i += 1
            while i < n and source[i].isdigit():
                i += 1
            tokens.append((source[start:i], start, i))
            continue
        matched_op = False
        for op in ("==", "!=", "<=", ">=", "&&", "||", "++", "--", "+=", "-=", "->"):
            if source.startswith(op, i):
                tokens.append((op, i, i + len(op)))
                i += len(op)
                matched_op = True
                break
        if not matched_op:
            tokens.append((ch, i, i + 1))
            i += 1
    return tokens


def _meaningful(tokens: list[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
    kept: list[tuple[str, int, int]] = []
    for token, start, end in tokens:
        if token.lower() in KEYWORDS:
            continue
        if len(token) == 1 and not token.isalnum():
            continue
        if token.isdigit() and len(token) <= 2:
            continue
        kept.append((token, start, end))
    return kept


def _jaccard(left: list[str], right: list[str], size: int = 4) -> float:
    if len(left) < size or len(right) < size:
        return 0.0
    left_sets = {tuple(left[index : index + size]) for index in range(len(left) - size + 1)}
    right_sets = {tuple(right[index : index + size]) for index in range(len(right) - size + 1)}
    union = left_sets | right_sets
    if not union:
        return 0.0
    return len(left_sets & right_sets) / float(len(union))


def _runs(
    left: list[tuple[str, int, int]],
    right: list[tuple[str, int, int]],
    minimum: int,
) -> list[tuple[int, int, int]]:
    rows = len(left)
    cols = len(right)
    if rows == 0 or cols == 0 or rows * cols > 250000:
        return []
    previous = [0] * (cols + 1)
    found: list[tuple[int, int, int]] = []
    for i in range(1, rows + 1):
        current = [0] * (cols + 1)
        for j in range(1, cols + 1):
            if left[i - 1][0] != right[j - 1][0]:
                continue
            current[j] = previous[j - 1] + 1
            continues = i < rows and j < cols and left[i][0] == right[j][0]
            if current[j] >= minimum and not continues:
                found.append((current[j], i - current[j], j - current[j]))
        previous = current
    found.sort(key=lambda item: item[0], reverse=True)
    chosen: list[tuple[int, int, int]] = []
    used_left: list[tuple[int, int]] = []
    used_right: list[tuple[int, int]] = []
    for length, left_index, right_index in found:
        left_span = (left_index, left_index + length)
        right_span = (right_index, right_index + length)
        if any(not (left_span[1] <= start or end <= left_span[0]) for start, end in used_left):
            continue
        if any(not (right_span[1] <= start or end <= right_span[0]) for start, end in used_right):
            continue
        chosen.append((length, left_index, right_index))
        used_left.append(left_span)
        used_right.append(right_span)
        if len(chosen) == 4:
            break
    return chosen


def _spans(tokens: list[tuple[str, int, int]], runs: list[tuple[int, int, int]], side: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for length, left_index, right_index in runs:
        index = left_index if side == 0 else right_index
        spans.append((tokens[index][1], tokens[index + length - 1][2]))
    spans.sort()
    return spans


def compare_sources(left_source: str, left_language: str, right_source: str, right_language: str) -> Optional[CodeMatch]:
    left = _meaningful(_scan(left_source or "", left_language or "python"))
    right = _meaningful(_scan(right_source or "", right_language or "python"))
    if len(left) < 8 or len(right) < 8:
        return None
    left_words = [token for token, _start, _end in left]
    right_words = [token for token, _start, _end in right]
    identical = left_words == right_words
    score = _jaccard(left_words, right_words)
    runs = _runs(left, right, 6)
    best = runs[0][0] if runs else 0
    shorter = float(min(len(left), len(right)))
    overlap = best / shorter if shorter else 0.0
    if identical and len(left) >= 8:
        percent = 100
    else:
        percent = int(round(100 * max(score, overlap)))
    suspicious = identical or (min(len(left), len(right)) >= 12 and percent >= 70)
    if not suspicious:
        return None
    if identical:
        display_runs = [(len(left), 0, 0)] if len(left) == len(right) else runs
        explanation = (
            "После удаления комментариев, пробелов и стандартных конструкций языка последовательности совпадают. "
            "Это повод для ручной проверки, а не доказательство списывания."
        )
    else:
        display_runs = runs
        explanation = (
            "Найден общий фрагмент из %d значимых токенов, сходство %d%%. "
            "Короткие и типовые конструкции не учитывались. Совпадение не доказывает списывание."
        ) % (best, percent)
    return CodeMatch(
        percent=percent,
        explanation=explanation,
        fragments=_spans(left, display_runs, 0),
        matched_fragments=_spans(right, display_runs, 1),
    )


def _same_team(contest: Contest, team_of: dict[int, Optional[int]], left: int, right: int) -> bool:
    if contest.participation_format != "team":
        return False
    left_team = team_of.get(left)
    right_team = team_of.get(right)
    return left_team is not None and left_team == right_team


def analyze_contest(db: Session, contest: Contest) -> None:
    db.query(FairPlayReport).filter(FairPlayReport.contest_id == contest.id).delete(synchronize_session=False)
    registrations = db.query(Registration).filter(Registration.contest_id == contest.id).all()
    team_of = {row.user_id: row.team_id for row in registrations}
    submissions = (
        db.query(Submission)
        .filter(Submission.contest_id == contest.id)
        .order_by(Submission.created_at.asc(), Submission.id.asc())
        .all()
    )
    grouped: dict[int, dict[int, list[Submission]]] = {}
    for submission in submissions:
        grouped.setdefault(submission.problem_id, {}).setdefault(submission.user_id, []).append(submission)
    for problem_id, by_user in grouped.items():
        user_ids = list(by_user)
        for left_index, left_user in enumerate(user_ids):
            for right_user in user_ids[left_index + 1 :]:
                if _same_team(contest, team_of, left_user, right_user):
                    continue
                best: Optional[CodeMatch] = None
                pair: Optional[tuple[Submission, Submission]] = None
                for left_submission in by_user[left_user][-8:]:
                    for right_submission in by_user[right_user][-8:]:
                        found = compare_sources(
                            left_submission.source_code,
                            left_submission.language,
                            right_submission.source_code,
                            right_submission.language,
                        )
                        if found is not None and (best is None or found.percent > best.percent):
                            best = found
                            pair = (left_submission, right_submission)
                if best is None or pair is None:
                    continue
                left_submission, right_submission = pair
                db.add(
                    FairPlayReport(
                        contest_id=contest.id,
                        problem_id=problem_id,
                        submission_id=left_submission.id,
                        matched_submission_id=right_submission.id,
                        similarity_percent=best.percent,
                        explanation=best.explanation,
                        status="attention",
                    )
                )
    contest.fairplay_analyzed_at = datetime.utcnow()
    db.commit()
