from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .config import BASE_DIR
from .database import Base, SessionLocal, engine
from .models import (
    Assessment,
    AssessmentQuestion,
    AssessmentVersion,
    LegacyReview,
    QuestionAnswer,
    SchemaMigration,
    Student,
    Submission,
    SubmissionReference,
)

MIGRATION_VERSION = "question_level_references_v1"


def _migration_applied(target_engine: Engine) -> bool:
    if not inspect(target_engine).has_table("schema_migrations"):
        return False
    with target_engine.connect() as connection:
        return (
            connection.exec_driver_sql(
                "SELECT 1 FROM schema_migrations WHERE version = ?",
                (MIGRATION_VERSION,),
            ).first()
            is not None
        )


def _backup_sqlite_database(target_engine: Engine) -> Optional[Path]:
    if target_engine.dialect.name != "sqlite":
        return None

    database_name = target_engine.url.database
    if not database_name or database_name == ":memory:":
        return None

    database_path = Path(database_name)
    if not database_path.is_absolute():
        database_path = Path.cwd() / database_path
    if not database_path.exists() or database_path.stat().st_size == 0:
        return None

    backup_dir = BASE_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"{database_path.stem}-before-question-migration-{timestamp}.db"

    source = sqlite3.connect(str(database_path))
    destination = sqlite3.connect(str(backup_path))
    try:
        source.backup(destination)
    except sqlite3.Error:
        destination.close()
        source.close()
        if backup_path.exists():
            backup_path.unlink()
        raise
    destination.close()
    source.close()
    return backup_path


def _record_review(db: Session, record_type: str, record_id: int, reason: str) -> None:
    db.add(LegacyReview(record_type=record_type, record_id=record_id, reason=reason))


def _backfill_legacy_records(db: Session) -> None:
    versions_by_assessment: dict[int, AssessmentVersion] = {}
    questions_by_assessment: dict[int, AssessmentQuestion] = {}

    for assessment in db.query(Assessment).order_by(Assessment.id).all():
        rubric = assessment.rubric_json if isinstance(assessment.rubric_json, list) else []
        is_complete = bool(
            (assessment.title or "").strip()
            and (assessment.subject or "").strip()
            and (assessment.question or "").strip()
            and (assessment.model_answer or "").strip()
            and rubric
            and float(assessment.max_marks or 0) > 0
        )
        version = AssessmentVersion(
            assessment_id=assessment.id,
            version_number=max(1, int(assessment.rubric_version or 1)),
            title=assessment.title or "",
            subject=assessment.subject or "",
            language=assessment.language or "English",
            status="locked" if is_complete else "needs_review",
            locked_at=assessment.created_at if is_complete else None,
        )
        db.add(version)
        db.flush()

        question = AssessmentQuestion(
            version_id=version.id,
            question_key="Q1",
            question_text=assessment.question or "",
            model_answer=assessment.model_answer or "",
            max_marks=float(assessment.max_marks or sum(
                float(item.get("max_marks", 0) or 0) for item in rubric
            )),
            rubric_json=rubric,
            display_order=0,
        )
        db.add(question)
        db.flush()
        versions_by_assessment[assessment.id] = version
        questions_by_assessment[assessment.id] = question

        if not is_complete:
            _record_review(
                db,
                "assessment",
                assessment.id,
                "Legacy assessment is missing a title, subject, question, model answer, rubric, or positive maximum mark.",
            )

    attempts: dict[tuple[int, str], int] = {}
    for submission in db.query(Submission).order_by(Submission.id).all():
        version = versions_by_assessment.get(submission.assessment_id)
        question = questions_by_assessment.get(submission.assessment_id)
        if not version or version.status != "locked" or not question:
            _record_review(db, "submission", submission.id, "The linked legacy assessment reference is incomplete and requires review.")
            continue
        if not (submission.student_id or "").strip():
            _record_review(db, "submission", submission.id, "Legacy submission has no student identifier.")
            continue
        if not (submission.student_answer or "").strip():
            _record_review(db, "submission", submission.id, "Legacy submission has no student answer.")
            continue

        external_id = submission.student_id.strip()
        student = db.query(Student).filter(Student.external_id == external_id).first()
        if student is None:
            student = Student(external_id=external_id)
            db.add(student)
            db.flush()

        attempt_key = (version.id, external_id)
        attempt_number = attempts.get(attempt_key, 0) + 1
        attempts[attempt_key] = attempt_number
        db.add(
            SubmissionReference(
                submission_id=submission.id,
                version_id=version.id,
                student_pk=student.id,
                attempt_number=attempt_number,
                is_legacy=True,
            )
        )
        feedback: dict[str, object] = {}
        if submission.feedback:
            try:
                parsed_feedback = json.loads(submission.feedback)
                feedback = parsed_feedback if isinstance(parsed_feedback, dict) else {"legacy_feedback": parsed_feedback}
            except (TypeError, json.JSONDecodeError):
                feedback = {"legacy_feedback": submission.feedback}

        db.add(
            QuestionAnswer(
                submission_id=submission.id,
                question_id=question.id,
                student_answer=submission.student_answer,
                ai_score=float(submission.total_score or 0),
                maximum_score=float(submission.maximum_score or question.max_marks or 0),
                ai_criteria_json=submission.criteria_json if isinstance(submission.criteria_json, list) else [],
                ai_feedback_json=feedback,
                ai_confidence=float(submission.ai_confidence or 0),
                review_status=submission.review_status or "needs_review",
                teacher_score=submission.human_score,
                teacher_notes=submission.teacher_notes,
                source_row_json={"legacy_submission_id": submission.id},
                created_at=submission.created_at,
            )
        )


def migrate_legacy_data(db: Session) -> None:
    if db.query(SchemaMigration).filter(SchemaMigration.version == MIGRATION_VERSION).first():
        return
    try:
        _backfill_legacy_records(db)
        db.add(SchemaMigration(version=MIGRATION_VERSION))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def run_migrations(target_engine: Engine = engine) -> None:
    if _migration_applied(target_engine):
        return
    try:
        _backup_sqlite_database(target_engine)
    except sqlite3.Error as error:
        raise RuntimeError(f"Could not create a pre-migration SQLite backup: {error}") from error

    Base.metadata.create_all(bind=target_engine)
    if target_engine is engine:
        db = SessionLocal()
        try:
            migrate_legacy_data(db)
        finally:
            db.close()
        return

    from sqlalchemy.orm import sessionmaker

    MigrationSession = sessionmaker(bind=target_engine, autocommit=False, autoflush=False)
    db = MigrationSession()
    try:
        migrate_legacy_data(db)
    finally:
        db.close()
