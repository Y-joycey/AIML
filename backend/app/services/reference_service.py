from __future__ import annotations

from datetime import datetime
from math import isclose
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from ..models import Assessment, AssessmentQuestion, AssessmentVersion


def create_draft_version(
    db: Session,
    assessment: Assessment,
    *,
    title: str,
    subject: str,
    language: str,
    questions: List[Dict[str, Any]],
    source_filename: str | None = None,
    source_sha256: str | None = None,
    source_path: str | None = None,
) -> AssessmentVersion:
    latest = (
        db.query(AssessmentVersion)
        .filter(AssessmentVersion.assessment_id == assessment.id)
        .order_by(AssessmentVersion.version_number.desc())
        .first()
    )
    version_number = (latest.version_number if latest else 0) + 1
    version = AssessmentVersion(
        assessment_id=assessment.id,
        version_number=version_number,
        title=title,
        subject=subject,
        language=language or "English",
        source_filename=source_filename,
        source_sha256=source_sha256,
        source_path=source_path,
        status="draft",
    )
    db.add(version)
    db.flush()
    replace_version_questions(db, version, questions)
    return version


def replace_version_questions(
    db: Session,
    version: AssessmentVersion,
    questions: List[Dict[str, Any]],
) -> None:
    if version.status not in {"draft", "needs_review"}:
        raise ValueError("A locked assessment reference cannot be edited.")
    question_ids = [str(item.get("question_id") or "").strip() for item in questions]
    if any(not question_id for question_id in question_ids) or len(question_ids) != len(set(question_ids)):
        raise ValueError("Every question must have a unique, non-empty question ID.")
    db.query(AssessmentQuestion).filter(AssessmentQuestion.version_id == version.id).delete()
    for index, item in enumerate(questions):
        rubric = item.get("rubric") if isinstance(item.get("rubric"), list) else []
        db.add(
            AssessmentQuestion(
                version_id=version.id,
                question_key=str(item.get("question_id") or "").strip(),
                question_text=str(item.get("question") or "").strip(),
                model_answer=str(item.get("model_answer") or "").strip(),
                max_marks=float(item.get("max_marks") or 0),
                rubric_json=rubric,
                display_order=index,
            )
        )
    db.flush()


def lock_version(db: Session, assessment: Assessment, version: AssessmentVersion) -> None:
    if version.assessment_id != assessment.id:
        raise ValueError("The reference version does not belong to this assessment.")
    if version.status == "locked":
        raise ValueError("This assessment reference is already locked.")
    if version.status not in {"draft", "needs_review"}:
        raise ValueError("This assessment reference cannot be locked until it is in draft status.")

    questions = (
        db.query(AssessmentQuestion)
        .filter(AssessmentQuestion.version_id == version.id)
        .order_by(AssessmentQuestion.display_order, AssessmentQuestion.id)
        .all()
    )
    validate_reference(version.title, version.subject, questions)

    version.status = "locked"
    version.locked_at = datetime.utcnow()
    first_question = questions[0]
    assessment.title = version.title
    assessment.subject = version.subject
    assessment.language = version.language
    assessment.question = first_question.question_text
    assessment.model_answer = first_question.model_answer
    assessment.max_marks = sum(float(question.max_marks) for question in questions)
    assessment.rubric_json = first_question.rubric_json
    assessment.rubric_version = version.version_number


def validate_reference(title: str, subject: str, questions: List[AssessmentQuestion]) -> None:
    if not title.strip() or not subject.strip():
        raise ValueError("Assessment title and subject are required before locking.")
    if not questions:
        raise ValueError("Add at least one question before locking the assessment.")

    seen_question_ids = set()
    for question in questions:
        key = question.question_key.strip()
        if not key or key in seen_question_ids:
            raise ValueError("Every question must have a unique, non-empty question ID.")
        seen_question_ids.add(key)
        if not question.question_text.strip() or not question.model_answer.strip():
            raise ValueError(f"Question {key} needs both a question and a model answer.")
        if question.max_marks <= 0:
            raise ValueError(f"Question {key} must have a positive maximum mark.")
        rubric = question.rubric_json if isinstance(question.rubric_json, list) else []
        if not rubric:
            raise ValueError(f"Question {key} must have at least one rubric criterion.")

        seen_criterion_ids = set()
        criterion_total = 0.0
        for criterion in rubric:
            criterion_id = str(criterion.get("id") or "").strip()
            criterion_title = str(criterion.get("title") or "").strip()
            criterion_description = str(criterion.get("description") or "").strip()
            criterion_maximum = float(criterion.get("max_marks") or 0)
            if (
                not criterion_id
                or not criterion_title
                or not criterion_description
                or criterion_id in seen_criterion_ids
            ):
                raise ValueError(f"Question {key} has a missing or duplicate rubric criterion field.")
            if criterion_maximum < 0:
                raise ValueError(f"Question {key} has a negative rubric maximum.")
            seen_criterion_ids.add(criterion_id)
            criterion_total += criterion_maximum
        if not isclose(criterion_total, float(question.max_marks), abs_tol=0.01):
            raise ValueError(
                f"Question {key} maximum marks must equal the sum of its rubric criteria."
            )
