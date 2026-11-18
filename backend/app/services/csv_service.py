from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Tuple

from ..models import AssessmentVersion


class CSVValidationError(ValueError):
    def __init__(self, message: str, errors: List[Dict[str, Any]] | None = None):
        super().__init__(message)
        self.errors = errors or []


def parse_student_csv(content: bytes, version: AssessmentVersion) -> Tuple[List[str], List[Dict[str, Any]], List[Dict[str, Any]]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CSVValidationError("CSV must use UTF-8 encoding.") from error

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not reader.fieldnames:
        raise CSVValidationError("CSV must include a header row.")

    headers = list(reader.fieldnames)
    canonical_headers: Dict[str, str] = {}
    for header in headers:
        canonical = header.strip().lower()
        if not canonical:
            raise CSVValidationError("CSV column names cannot be empty.")
        if canonical in canonical_headers:
            raise CSVValidationError(f"CSV has duplicate column names after trimming: {header}.")
        canonical_headers[canonical] = header

    required = {"student_id", "student_answer"}
    if not required.issubset(canonical_headers):
        raise CSVValidationError("CSV must contain student_id and student_answer columns.")
    disallowed_score_columns = {"human_score", "teacher_score", "teacher_marks"}
    if disallowed_score_columns.intersection(canonical_headers):
        raise CSVValidationError(
            "AI grading CSVs cannot contain teacher score columns. Enter teacher marks on the Teacher Grading page."
        )

    questions = sorted(version.questions, key=lambda question: (question.display_order, question.id))
    question_by_key = {question.question_key: question for question in questions}
    has_question_id = "question_id" in canonical_headers
    if len(question_by_key) > 1 and not has_question_id:
        raise CSVValidationError("Multi-question assessments require a question_id column.")
    default_question = next(iter(question_by_key.values())) if len(question_by_key) == 1 else None

    rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    seen_pairs = set()
    for row_number, raw_row in enumerate(reader, start=2):
        if None in raw_row:
            errors.append({"row": row_number, "error": "Row contains more values than the header."})
            continue
        source_row = {header: raw_row.get(header, "") or "" for header in headers}
        student_id = str(raw_row.get(canonical_headers["student_id"], "") or "").strip()
        student_answer = str(raw_row.get(canonical_headers["student_answer"], "") or "").strip()
        question_key = (
            str(raw_row.get(canonical_headers["question_id"], "") or "").strip()
            if has_question_id
            else (default_question.question_key if default_question else "")
        )
        if not student_id:
            errors.append({"row": row_number, "error": "Missing student_id."})
            continue
        if len(student_id) > 120:
            errors.append({"row": row_number, "student_id": student_id[:120], "error": "student_id exceeds 120 characters."})
            continue
        if not student_answer:
            errors.append({"row": row_number, "student_id": student_id, "error": "Empty student_answer."})
            continue
        question = question_by_key.get(question_key)
        if question is None:
            errors.append(
                {
                    "row": row_number,
                    "student_id": student_id,
                    "error": f"Unknown question_id '{question_key}'.",
                }
            )
            continue
        pair = (student_id, question.id)
        if pair in seen_pairs:
            errors.append(
                {
                    "row": row_number,
                    "student_id": student_id,
                    "error": f"Duplicate answer for question {question_key} in this CSV.",
                }
            )
            continue
        seen_pairs.add(pair)
        rows.append(
            {
                "student_id": student_id,
                "question_id": question.id,
                "question_key": question.question_key,
                "student_answer": student_answer,
                "source_row": source_row,
            }
        )
    if not rows and not errors:
        errors.append({"row": 0, "error": "CSV contains no student answer rows."})
    return headers, rows, errors
