from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .config import BASE_DIR
from .database import SessionLocal, get_db
from .migrations import run_migrations
from .models import (
    Assessment,
    AssessmentQuestion,
    AssessmentVersion,
    CSVImportBatch,
    LegacyReview,
    QuestionAnswer,
    Student,
    Submission,
    SubmissionReference,
)
from .schemas import (
    AssessmentInput,
    AssessmentReviewInput,
    GradeSingleSubmissionRequest,
    RubricVersionUpdate,
    TeacherMarkInput,
)
from .services.analytics_service import build_dashboard
from .services.csv_service import CSVValidationError, parse_student_csv
from .services.document_parser import DocumentParserError, extract_document_text
from .services.grading_service import calculate_qwk, evaluate_question
from .services.local_model_service import LocalModelError, extract_assessment
from .services.reference_service import create_draft_version, lock_version, replace_version_questions

app = FastAPI(title="GradeSense AI API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

run_migrations()

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
UPLOAD_DIR = BASE_DIR / "uploads"


def _ordered_questions(db: Session, version_id: int) -> List[AssessmentQuestion]:
    return (
        db.query(AssessmentQuestion)
        .filter(AssessmentQuestion.version_id == version_id)
        .order_by(AssessmentQuestion.display_order, AssessmentQuestion.id)
        .all()
    )


def _question_payload(question: AssessmentQuestion) -> Dict[str, Any]:
    return {
        "question_id": question.question_key,
        "question": question.question_text,
        "model_answer": question.model_answer,
        "max_marks": float(question.max_marks or 0),
        "rubric": question.rubric_json or [],
    }


def _version_payload(db: Session, version: AssessmentVersion) -> Dict[str, Any]:
    questions = _ordered_questions(db, version.id)
    return {
        "id": version.id,
        "version_number": version.version_number,
        "title": version.title,
        "subject": version.subject,
        "language": version.language,
        "status": version.status,
        "is_locked": version.status == "locked",
        "source_filename": version.source_filename,
        "locked_at": version.locked_at.isoformat() if version.locked_at else None,
        "questions": [_question_payload(question) for question in questions],
    }


def _assessment_payload(db: Session, assessment: Assessment) -> Dict[str, Any]:
    versions = (
        db.query(AssessmentVersion)
        .filter(AssessmentVersion.assessment_id == assessment.id)
        .order_by(AssessmentVersion.version_number.desc())
        .all()
    )
    active_version = next((item for item in versions if item.status == "locked"), None)
    latest_version = versions[0] if versions else None
    version = active_version or latest_version
    if version is None:
        question = assessment.question or ""
        model_answer = assessment.model_answer or ""
        rubric = assessment.rubric_json or []
        max_marks = float(assessment.max_marks or 0)
        questions = []
        status = "legacy_unmigrated"
        version_id = None
        is_locked = False
        source_filename = None
    else:
        question_rows = _ordered_questions(db, version.id)
        first_question = question_rows[0] if question_rows else None
        question = first_question.question_text if first_question else ""
        model_answer = first_question.model_answer if first_question else ""
        rubric = first_question.rubric_json if first_question else []
        max_marks = sum(float(item.max_marks or 0) for item in question_rows)
        questions = [_question_payload(item) for item in question_rows]
        status = version.status
        version_id = version.id
        is_locked = active_version is not None
        source_filename = version.source_filename
        if latest_version and latest_version.status in {"draft", "needs_review"} and active_version is not None:
            status = "locked_with_draft"
    return {
        "id": assessment.id,
        "title": version.title if version else assessment.title,
        "subject": version.subject if version else assessment.subject,
        "language": version.language if version else assessment.language,
        "question": question,
        "model_answer": model_answer,
        "max_marks": max_marks,
        "rubric": rubric,
        "rubric_version": version.version_number if version else assessment.rubric_version,
        "version_id": version_id,
        "question_count": len(questions),
        "questions": questions,
        "reference_status": status,
        "is_locked": is_locked,
        "source_filename": source_filename,
        "draft_version_id": (
            latest_version.id
            if latest_version is not None and latest_version.status in {"draft", "needs_review"}
            else None
        ),
        "version_history": [
            {
                "id": item.id,
                "version_number": item.version_number,
                "status": item.status,
                "source_filename": item.source_filename,
                "locked_at": item.locked_at.isoformat() if item.locked_at else None,
            }
            for item in versions
        ],
        "created_at": assessment.created_at.isoformat() if assessment.created_at else "",
    }


def _get_locked_version(db: Session, assessment_id: int, version_id: Optional[int]) -> AssessmentVersion:
    if db.query(Assessment.id).filter(Assessment.id == assessment_id).first() is None:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    query = db.query(AssessmentVersion).filter(
        AssessmentVersion.assessment_id == assessment_id,
        AssessmentVersion.status == "locked",
    )
    if version_id is not None:
        query = query.filter(AssessmentVersion.id == version_id)
    else:
        query = query.order_by(AssessmentVersion.version_number.desc())
    version = query.first()
    if version is None:
        raise HTTPException(
            status_code=409,
            detail="This assessment has no locked reference version. Review and lock its questions, answers, and rubric first.",
        )
    return version


def _ensure_student(db: Session, external_id: str) -> Student:
    student = db.query(Student).filter(Student.external_id == external_id).first()
    if student is None:
        student = Student(external_id=external_id)
        db.add(student)
        db.flush()
    return student


def _question_evaluation_input(question: AssessmentQuestion) -> Dict[str, Any]:
    return {
        "question": question.question_text,
        "model_answer": question.model_answer,
        "max_marks": float(question.max_marks or 0),
        "rubric": question.rubric_json or [],
    }


def _normalize_document_name(filename: str) -> str:
    return Path(filename.replace("\\", "/")).name[:255]


def _validate_document(content: bytes, filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in {".pdf", ".jpg", ".jpeg"}:
        raise HTTPException(status_code=400, detail="Only PDF, JPG, and JPEG documents are accepted.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Assessment documents must be 15 MB or smaller.")
    if extension == ".pdf" and not content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="The uploaded file does not have a valid PDF signature.")
    if extension in {".jpg", ".jpeg"} and not content.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=400, detail="The uploaded file does not have a valid JPEG signature.")
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded document is empty.")
    return extension


def _read_csv(file_name: str, content: bytes, version: AssessmentVersion) -> Dict[str, Any]:
    if Path(file_name).suffix.lower() != ".csv":
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="CSV files must be 15 MB or smaller.")
    try:
        headers, rows, errors = parse_student_csv(content, version)
    except CSVValidationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {
        "headers": headers,
        "rows": rows,
        "errors": errors,
        "content_sha256": hashlib.sha256(content).hexdigest(),
        "filename": _normalize_document_name(file_name),
    }


def seed_demo_assessment(db: Session) -> None:
    if db.query(Assessment).count() > 0:
        return

    assessment = Assessment(
        title="Short Writing Reflection",
        subject="English Literature",
        language="English",
        question="Explain how the character changed over the course of the story and support your answer with evidence.",
        model_answer="The character becomes more confident and responsible by learning from mistakes, accepting advice, and acting with courage when facing conflict.",
        max_marks=12,
        rubric_version=1,
        rubric_json=[
            {
                "id": "C1",
                "title": "Understanding of change",
                "description": "Shows a clear understanding of the character's development",
                "max_marks": 5,
                "partial_credit": "Award credit for a basic or partial explanation of change",
            },
            {
                "id": "C2",
                "title": "Evidence and examples",
                "description": "Supports ideas with evidence from the text",
                "max_marks": 4,
                "partial_credit": "Award partial credit for relevant references",
            },
            {
                "id": "C3",
                "title": "Organisation and clarity",
                "description": "Presents ideas clearly and logically",
                "max_marks": 3,
                "partial_credit": "Award partial credit for a mostly clear response",
            },
        ],
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    version = AssessmentVersion(
        assessment_id=assessment.id,
        version_number=1,
        title=assessment.title,
        subject=assessment.subject,
        language=assessment.language,
        status="locked",
        locked_at=assessment.created_at,
    )
    db.add(version)
    db.flush()
    question = AssessmentQuestion(
        version_id=version.id,
        question_key="Q1",
        question_text=assessment.question,
        model_answer=assessment.model_answer,
        max_marks=assessment.max_marks,
        rubric_json=assessment.rubric_json,
        display_order=0,
    )
    db.add(question)
    db.flush()

    sample_submission = Submission(
        assessment_id=assessment.id,
        student_id="S-101",
        student_answer="The character grows from being unsure to becoming brave and responsible after learning from mistakes and trying again.",
        human_score=10,
        teacher_notes="Very solid response.",
        total_score=9.8,
        maximum_score=12,
        percentage=82,
        review_status="approved",
        feedback=json.dumps({
            "strengths": "You showed a clear understanding of character change.",
            "missing_concepts": "You could include more textual evidence.",
            "suggestions": ["Add one direct reference from the story.", "Explain how the change affects the ending."],
            "overall_feedback": "Strong response with clear development.",
        }),
        criteria_json=[
            {
                "criterion_id": "C1",
                "criterion_title": "Understanding of change",
                "awarded_marks": 5,
                "max_marks": 5,
                "rationale": "Clear explanation of growth and learning.",
                "evidence": "becomes brave and responsible",
                "confidence": 0.88,
                "needs_review": False,
            },
            {
                "criterion_id": "C2",
                "criterion_title": "Evidence and examples",
                "awarded_marks": 3,
                "max_marks": 4,
                "rationale": "Some evidence but could be stronger.",
                "evidence": "after learning from mistakes",
                "confidence": 0.71,
                "needs_review": False,
            },
            {
                "criterion_id": "C3",
                "criterion_title": "Organisation and clarity",
                "awarded_marks": 2,
                "max_marks": 3,
                "rationale": "Mostly clear and logical.",
                "evidence": "The character grows from being unsure...",
                "confidence": 0.76,
                "needs_review": False,
            },
        ],
        ai_confidence=0.78,
        discordance=0.0,
    )
    db.add(sample_submission)
    db.flush()
    student = _ensure_student(db, sample_submission.student_id)
    db.add(
        SubmissionReference(
            submission_id=sample_submission.id,
            version_id=version.id,
            student_pk=student.id,
            attempt_number=1,
        )
    )
    db.add(
        QuestionAnswer(
            submission_id=sample_submission.id,
            question_id=question.id,
            student_answer=sample_submission.student_answer,
            ai_score=sample_submission.total_score,
            maximum_score=sample_submission.maximum_score,
            ai_criteria_json=sample_submission.criteria_json,
            ai_feedback_json=json.loads(sample_submission.feedback or "{}"),
            ai_confidence=sample_submission.ai_confidence,
            review_status=sample_submission.review_status,
            teacher_score=sample_submission.human_score,
            teacher_notes=sample_submission.teacher_notes,
            source_row_json={"seeded": True},
        )
    )
    db.commit()


@app.on_event("startup")
def startup_event() -> None:
    db = SessionLocal()
    try:
        seed_demo_assessment(db)
    finally:
        db.close()


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "app": "GradeSense AI"}


@app.get("/api/assessments")
def list_assessments(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    assessments = db.query(Assessment).order_by(Assessment.created_at.desc()).all()
    return [_assessment_payload(db, assessment) for assessment in assessments]


@app.get("/api/assessments/{assessment_id}")
def get_assessment(assessment_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return _assessment_payload(db, assessment)


@app.get("/api/assessments/{assessment_id}/versions/{version_id}")
def get_assessment_version(
    assessment_id: int,
    version_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    version = (
        db.query(AssessmentVersion)
        .filter(
            AssessmentVersion.assessment_id == assessment_id,
            AssessmentVersion.id == version_id,
        )
        .first()
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Assessment version not found.")
    return _version_payload(db, version)


@app.post("/api/assessments")
def create_assessment(payload: AssessmentInput, db: Session = Depends(get_db)) -> Dict[str, Any]:
    rubric = [criterion.model_dump() for criterion in payload.rubric]
    total_marks = sum(float(item["max_marks"]) for item in rubric)
    assessment = Assessment(
        title=payload.title,
        subject=payload.subject,
        language=payload.language,
        question=payload.question,
        model_answer=payload.model_answer,
        max_marks=total_marks,
        rubric_version=1,
        rubric_json=rubric,
    )
    db.add(assessment)
    db.flush()
    version = AssessmentVersion(
        assessment_id=assessment.id,
        version_number=1,
        title=assessment.title,
        subject=assessment.subject,
        language=assessment.language,
        status="draft",
    )
    db.add(version)
    db.flush()
    question = AssessmentQuestion(
        version_id=version.id,
        question_key="Q1",
        question_text=assessment.question,
        model_answer=assessment.model_answer,
        max_marks=total_marks,
        rubric_json=rubric,
        display_order=0,
    )
    db.add(question)
    db.flush()
    try:
        lock_version(db, assessment, version)
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error)) from error
    db.commit()
    db.refresh(assessment)
    return _assessment_payload(db, assessment)


@app.post("/api/assessments/upload")
async def upload_assessment_document(
    file: UploadFile = File(...),
    title: str = Form(default=""),
    subject: str = Form(default=""),
    language: str = Form(default="English"),
    ocr_language: str = Form(default="eng"),
    assessment_id: Optional[int] = Form(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    filename = _normalize_document_name(file.filename or "assessment.pdf")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    extension = _validate_document(content, filename)
    try:
        extracted_text, extraction_method = extract_document_text(content, filename, ocr_language)
    except DocumentParserError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    try:
        extracted = extract_assessment(extracted_text)
    except LocalModelError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error

    existing_assessment = None
    if assessment_id is not None:
        existing_assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
        if existing_assessment is None:
            raise HTTPException(status_code=404, detail="Assessment not found.")

    final_title = title.strip() or extracted["title"] or (existing_assessment.title if existing_assessment else Path(filename).stem)
    final_subject = subject.strip() or extracted["subject"] or (existing_assessment.subject if existing_assessment else "")
    final_language = language.strip() or extracted["language"] or "English"
    storage_name = f"{uuid4().hex}{extension}"
    storage_path = UPLOAD_DIR / storage_name
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(content)

    try:
        if existing_assessment is None:
            first_question = extracted["questions"][0]
            assessment = Assessment(
                title=final_title,
                subject=final_subject,
                language=final_language,
                question=first_question["question"],
                model_answer=first_question["model_answer"],
                max_marks=sum(float(item.get("max_marks", 0) or 0) for item in extracted["questions"]),
                rubric_version=0,
                rubric_json=first_question["rubric"],
            )
            db.add(assessment)
            db.flush()
        else:
            assessment = existing_assessment

        version = create_draft_version(
            db,
            assessment,
            title=final_title,
            subject=final_subject,
            language=final_language,
            questions=extracted["questions"],
            source_filename=filename,
            source_sha256=hashlib.sha256(content).hexdigest(),
            source_path=f"uploads/{storage_name}",
        )
        db.commit()
        db.refresh(version)
    except SQLAlchemyError:
        db.rollback()
        storage_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="The assessment draft could not be saved.")

    return {
        "assessment_id": assessment.id,
        "version": _version_payload(db, version),
        "extraction_method": extraction_method,
        "message": "Review the extracted questions, answers, and rubrics before locking this version.",
    }


@app.put("/api/assessments/{assessment_id}/versions/{version_id}")
def update_assessment_review(
    assessment_id: int,
    version_id: int,
    payload: AssessmentReviewInput,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    version = db.query(AssessmentVersion).filter(AssessmentVersion.id == version_id).first()
    if assessment is None or version is None or version.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="Assessment draft not found.")
    if version.status not in {"draft", "needs_review"}:
        raise HTTPException(status_code=409, detail="Locked assessment references are immutable.")
    question_data = [
        {
            "question_id": item.question_id,
            "question": item.question,
            "model_answer": item.model_answer,
            "max_marks": item.max_marks,
            "rubric": [criterion.model_dump() for criterion in item.rubric],
        }
        for item in payload.questions
    ]
    try:
        replace_version_questions(db, version, question_data)
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error)) from error
    version.title = payload.title.strip()
    version.subject = payload.subject.strip()
    version.language = payload.language.strip() or "English"
    version.status = "draft"
    db.commit()
    return _version_payload(db, version)


@app.post("/api/assessments/{assessment_id}/versions/{version_id}/lock")
def lock_assessment_reference(
    assessment_id: int,
    version_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    version = db.query(AssessmentVersion).filter(AssessmentVersion.id == version_id).first()
    if assessment is None or version is None or version.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="Assessment draft not found.")
    try:
        lock_version(db, assessment, version)
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error)) from error
    db.commit()
    return _assessment_payload(db, assessment)


@app.post("/api/submissions/grade")
def grade_submission(payload: GradeSingleSubmissionRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    raise HTTPException(
        status_code=409,
        detail="AI grading is CSV-only. Upload student answers on the AI Grading page, then enter teacher marks separately.",
    )


@app.post("/api/submissions/csv-preview")
async def preview_csv(
    assessment_id: int = Form(...),
    version_id: Optional[int] = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    filename = _normalize_document_name(file.filename or "answers.csv")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    version = _get_locked_version(db, assessment_id, version_id)
    parsed = _read_csv(filename, content, version)
    student_by_external_id = {
        student.external_id: student
        for student in db.query(Student).filter(
            Student.external_id.in_({row["student_id"] for row in parsed["rows"]})
        ).all()
    } if parsed["rows"] else {}
    conflicts = []
    for row in parsed["rows"]:
        student = student_by_external_id.get(row["student_id"])
        if student is None:
            continue
        existing = (
            db.query(QuestionAnswer.id)
            .join(SubmissionReference, SubmissionReference.submission_id == QuestionAnswer.submission_id)
            .filter(
                SubmissionReference.version_id == version.id,
                SubmissionReference.student_pk == student.id,
                QuestionAnswer.question_id == row["question_id"],
            )
            .first()
        )
        if existing:
            conflicts.append({"student_id": row["student_id"], "question_id": row["question_key"]})
    prior_batch = (
        db.query(CSVImportBatch.id)
        .filter(
            CSVImportBatch.version_id == version.id,
            CSVImportBatch.content_sha256 == parsed["content_sha256"],
        )
        .first()
    )
    question_by_id = {question.id: question for question in _ordered_questions(db, version.id)}
    preview_rows = [
        {
            "student_id": row["student_id"],
            "question_id": row["question_key"],
            "question": question_by_id[row["question_id"]].question_text,
            "student_answer": row["student_answer"],
            "source_columns": row["source_row"],
        }
        for row in parsed["rows"]
    ]
    return {
        "rows": preview_rows,
        "errors": parsed["errors"],
        "headers": parsed["headers"],
        "content_sha256": parsed["content_sha256"],
        "filename": parsed["filename"],
        "version_id": version.id,
        "duplicate_file": prior_batch is not None,
        "existing_answer_conflicts": conflicts,
        "requires_new_attempt": bool(prior_batch or conflicts),
        "message": "All original columns are retained for the teacher-mark export.",
    }


@app.post("/api/submissions/import")
async def import_csv_rows(
    assessment_id: int = Form(...),
    version_id: Optional[int] = Form(default=None),
    start_new_attempt: bool = Form(default=False),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    filename = _normalize_document_name(file.filename or "answers.csv")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    version = _get_locked_version(db, assessment_id, version_id)
    parsed = _read_csv(filename, content, version)
    if parsed["errors"]:
        raise HTTPException(
            status_code=422,
            detail={"message": "Fix every CSV validation error before importing.", "errors": parsed["errors"]},
        )
    duplicate_file = (
        db.query(CSVImportBatch.id)
        .filter(
            CSVImportBatch.version_id == version.id,
            CSVImportBatch.content_sha256 == parsed["content_sha256"],
        )
        .first()
    )
    if duplicate_file and not start_new_attempt:
        raise HTTPException(
            status_code=409,
            detail="This CSV was already imported. Select 'Import as a new attempt' to preserve it as a separate attempt.",
        )

    students = {
        student.external_id: student
        for student in db.query(Student).filter(
            Student.external_id.in_({row["student_id"] for row in parsed["rows"]})
        ).all()
    } if parsed["rows"] else {}
    conflicts = []
    for row in parsed["rows"]:
        student = students.get(row["student_id"])
        if student is None:
            continue
        exists = (
            db.query(QuestionAnswer.id)
            .join(SubmissionReference, SubmissionReference.submission_id == QuestionAnswer.submission_id)
            .filter(
                SubmissionReference.version_id == version.id,
                SubmissionReference.student_pk == student.id,
                QuestionAnswer.question_id == row["question_id"],
            )
            .first()
        )
        if exists:
            conflicts.append({"student_id": row["student_id"], "question_id": row["question_key"]})
    if conflicts and not start_new_attempt:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Some student/question answers already exist. Select 'Import as a new attempt' to keep both attempts.",
                "conflicts": conflicts,
            },
        )

    question_by_id = {question.id: question for question in _ordered_questions(db, version.id)}
    evaluated_rows = []
    try:
        for row in parsed["rows"]:
            question = question_by_id[row["question_id"]]
            evaluation = evaluate_question(_question_evaluation_input(question), row["student_answer"])
            evaluated_rows.append({**row, "question": question, "evaluation": evaluation})
    except LocalModelError as error:
        db.rollback()
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Local grading response was invalid: {error}") from error

    try:
        batch = CSVImportBatch(
            version_id=version.id,
            source_filename=parsed["filename"],
            content_sha256=parsed["content_sha256"],
            headers_json=parsed["headers"],
            is_new_attempt=start_new_attempt,
        )
        db.add(batch)
        db.flush()
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for row in evaluated_rows:
            grouped.setdefault(row["student_id"], []).append(row)

        created_rows = []
        for external_id, answer_rows in grouped.items():
            student = students.get(external_id) or _ensure_student(db, external_id)
            current_attempt = (
                db.query(func.max(SubmissionReference.attempt_number))
                .filter(
                    SubmissionReference.version_id == version.id,
                    SubmissionReference.student_pk == student.id,
                )
                .scalar()
                or 0
            )
            total_score = round(sum(row["evaluation"]["total_score"] for row in answer_rows), 2)
            maximum_score = round(sum(row["evaluation"]["maximum_score"] for row in answer_rows), 2)
            submission = Submission(
                assessment_id=assessment_id,
                student_id=external_id,
                student_answer="\n\n".join(
                    f"[{row['question'].question_key}] {row['student_answer']}" for row in answer_rows
                ),
                human_score=None,
                total_score=total_score,
                maximum_score=maximum_score,
                percentage=round(total_score / maximum_score * 100, 2) if maximum_score > 0 else 0,
                review_status=(
                    "needs_review"
                    if any(row["evaluation"]["review_status"] == "needs_review" for row in answer_rows)
                    else "approved"
                ),
                feedback=json.dumps(
                    {
                        row["question"].question_key: row["evaluation"]["feedback"]
                        for row in answer_rows
                    }
                ),
                criteria_json=[
                    {"question_id": row["question"].question_key, **criterion}
                    for row in answer_rows
                    for criterion in row["evaluation"]["criteria"]
                ],
                ai_confidence=round(
                    sum(row["evaluation"]["confidence"] for row in answer_rows) / len(answer_rows),
                    2,
                ),
                discordance=0,
            )
            db.add(submission)
            db.flush()
            db.add(
                SubmissionReference(
                    submission_id=submission.id,
                    version_id=version.id,
                    student_pk=student.id,
                    import_batch_id=batch.id,
                    attempt_number=int(current_attempt) + 1,
                )
            )
            for row in answer_rows:
                evaluation = row["evaluation"]
                db.add(
                    QuestionAnswer(
                        submission_id=submission.id,
                        question_id=row["question"].id,
                        student_answer=row["student_answer"],
                        ai_score=evaluation["total_score"],
                        maximum_score=evaluation["maximum_score"],
                        ai_criteria_json=evaluation["criteria"],
                        ai_feedback_json=evaluation["feedback"],
                        ai_confidence=evaluation["confidence"],
                        review_status=evaluation["review_status"],
                        source_row_json=row["source_row"],
                    )
                )
            created_rows.append(
                {
                    "student_id": external_id,
                    "attempt_number": int(current_attempt) + 1,
                    "score": total_score,
                    "maximum_score": maximum_score,
                }
            )
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="The CSV batch could not be saved.") from error
    return {"created": len(created_rows), "batch_id": batch.id, "rows": created_rows}


@app.get("/api/assessments/{assessment_id}/question-answers")
def list_question_answers(
    assessment_id: int,
    version_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    query = (
        db.query(QuestionAnswer)
        .join(Submission, Submission.id == QuestionAnswer.submission_id)
        .join(SubmissionReference, SubmissionReference.submission_id == Submission.id)
        .join(AssessmentVersion, AssessmentVersion.id == SubmissionReference.version_id)
        .join(AssessmentQuestion, AssessmentQuestion.id == QuestionAnswer.question_id)
        .filter(Submission.assessment_id == assessment_id)
    )
    if version_id is not None:
        query = query.filter(SubmissionReference.version_id == version_id)
    answers = query.order_by(Submission.created_at.desc(), AssessmentQuestion.display_order).all()
    result = []
    for answer in answers:
        submission = answer.submission
        reference = submission.reference
        question = answer.question
        result.append(
            {
                "id": answer.id,
                "submission_id": submission.id,
                "student_id": submission.student_id,
                "attempt_number": reference.attempt_number,
                "batch_id": reference.import_batch_id,
                "version_id": reference.version_id,
                "question_id": question.question_key,
                "question": question.question_text,
                "student_answer": answer.student_answer,
                "ai_score": answer.ai_score,
                "maximum_score": answer.maximum_score,
                "ai_criteria": answer.ai_criteria_json or [],
                "ai_feedback": answer.ai_feedback_json or {},
                "ai_confidence": answer.ai_confidence,
                "review_status": answer.review_status,
                "teacher_score": answer.teacher_score,
                "teacher_notes": answer.teacher_notes or "",
                "created_at": answer.created_at.isoformat() if answer.created_at else "",
            }
        )
    return result


@app.put("/api/question-answers/{question_answer_id}/teacher-mark")
def save_teacher_mark(
    question_answer_id: int,
    payload: TeacherMarkInput,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    answer = db.query(QuestionAnswer).filter(QuestionAnswer.id == question_answer_id).first()
    if answer is None:
        raise HTTPException(status_code=404, detail="Question answer not found.")
    if answer.teacher_score is not None and payload.score == answer.teacher_score and (payload.notes or "") == (answer.teacher_notes or ""):
        return {"id": answer.id, "teacher_score": answer.teacher_score, "message": "Teacher mark is unchanged."}
    if payload.score > answer.maximum_score:
        raise HTTPException(
            status_code=422,
            detail=f"Teacher score cannot exceed the question maximum of {answer.maximum_score}.",
        )
    submission = answer.submission
    reference = submission.reference
    if reference is None or reference.version.status != "locked":
        raise HTTPException(status_code=409, detail="Teacher marks require a locked assessment reference.")

    answer.teacher_score = payload.score
    answer.teacher_notes = payload.notes
    db.flush()
    all_answers = db.query(QuestionAnswer).filter(QuestionAnswer.submission_id == submission.id).all()
    if all(item.teacher_score is not None for item in all_answers):
        teacher_total = round(sum(float(item.teacher_score) for item in all_answers), 2)
        submission.human_score = teacher_total
        submission.teacher_notes = "\n".join(
            item.teacher_notes for item in all_answers if item.teacher_notes
        )
        threshold = max(2.0, 0.2 * float(submission.maximum_score or 0))
        submission.discordance = int(abs(float(submission.total_score or 0) - teacher_total) > threshold)
    else:
        submission.human_score = None
        submission.teacher_notes = None
        submission.discordance = 0
    db.commit()
    return {
        "id": answer.id,
        "teacher_score": answer.teacher_score,
        "teacher_notes": answer.teacher_notes or "",
        "submission_teacher_score": submission.human_score,
        "message": "Teacher mark saved independently of the AI score.",
    }


@app.get("/api/submissions/export/{batch_id}")
def export_marked_csv(batch_id: int, db: Session = Depends(get_db)) -> StreamingResponse:
    batch = db.query(CSVImportBatch).filter(CSVImportBatch.id == batch_id).first()
    if batch is None:
        raise HTTPException(status_code=404, detail="CSV import batch not found.")
    headers = list(batch.headers_json or [])
    canonical_headers = {str(header).strip().lower() for header in headers}
    export_headers = headers.copy()
    if "question_id" not in canonical_headers:
        export_headers.append("question_id")
    if "teacher_score" not in canonical_headers:
        export_headers.append("teacher_score")

    answer_rows = (
        db.query(QuestionAnswer)
        .join(SubmissionReference, SubmissionReference.submission_id == QuestionAnswer.submission_id)
        .filter(SubmissionReference.import_batch_id == batch.id)
        .join(AssessmentQuestion, AssessmentQuestion.id == QuestionAnswer.question_id)
        .order_by(QuestionAnswer.submission_id, AssessmentQuestion.display_order)
        .all()
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=export_headers, extrasaction="ignore")
    writer.writeheader()
    for answer in answer_rows:
        row = dict(answer.source_row_json or {})
        if "question_id" not in canonical_headers:
            row["question_id"] = answer.question.question_key
        row["teacher_score"] = "" if answer.teacher_score is None else answer.teacher_score
        writer.writerow(row)
    output.seek(0)
    download_name = f"teacher-marks-{batch.id}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@app.get("/api/legacy-review")
def list_legacy_review(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    return [
        {
            "id": item.id,
            "record_type": item.record_type,
            "record_id": item.record_id,
            "reason": item.reason,
            "status": item.status,
        }
        for item in db.query(LegacyReview).order_by(LegacyReview.id).all()
    ]


@app.get("/api/results/{assessment_id}")
def list_results(assessment_id: int, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    submissions = db.query(Submission).filter(Submission.assessment_id == assessment_id).order_by(Submission.created_at.desc()).all()
    results = []
    for submission in submissions:
        feedback = json.loads(submission.feedback or '{}') if submission.feedback else {}
        results.append(
            {
                "id": submission.id,
                "student_id": submission.student_id,
                "student_answer": submission.student_answer,
                "total_score": submission.total_score,
                "maximum_score": submission.maximum_score,
                "percentage": submission.percentage,
                "review_status": submission.review_status,
                "criteria": submission.criteria_json or [],
                "human_score": submission.human_score,
                "teacher_notes": submission.teacher_notes,
                "feedback": feedback,
                "confidence": submission.ai_confidence,
                "discordance": submission.discordance,
                "version_id": submission.reference.version_id if submission.reference else None,
                "version_number": submission.reference.version.version_number if submission.reference else None,
                "attempt_number": submission.reference.attempt_number if submission.reference else None,
                "created_at": submission.created_at.isoformat(),
            }
        )
    return results


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)) -> Dict[str, Any]:
    versions = db.query(AssessmentVersion).filter(AssessmentVersion.status == "locked").all()
    latest_versions: Dict[int, AssessmentVersion] = {}
    for version in versions:
        current = latest_versions.get(version.assessment_id)
        if current is None or version.version_number > current.version_number:
            latest_versions[version.assessment_id] = version
    submissions = []
    for reference in (
        db.query(SubmissionReference)
        .join(Submission, Submission.id == SubmissionReference.submission_id)
        .all()
    ):
        version = latest_versions.get(reference.version.assessment_id)
        if version is None or version.id != reference.version_id:
            continue
        submission = reference.submission
        submissions.append(
            {
                "student_id": submission.student_id,
                "assessment_title": reference.version.title,
                "total_score": submission.total_score,
                "percentage": submission.percentage,
                "review_status": submission.review_status,
                "created_at": submission.created_at.strftime("%Y-%m-%d"),
            }
        )
    dashboard = build_dashboard(
        [{"id": item.assessment_id, "title": item.title} for item in latest_versions.values()],
        submissions,
    )
    return dashboard


@app.post("/api/assessments/{assessment_id}/rubric-version")
def create_rubric_version(payload: RubricVersionUpdate, db: Session = Depends(get_db)) -> Dict[str, Any]:
    assessment = db.query(Assessment).filter(Assessment.id == payload.assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    previous = (
        db.query(AssessmentVersion)
        .filter(
            AssessmentVersion.assessment_id == assessment.id,
            AssessmentVersion.status == "locked",
        )
        .order_by(AssessmentVersion.version_number.desc())
        .first()
    )
    if previous is None:
        raise HTTPException(status_code=409, detail="Lock a complete assessment reference before creating a rubric version.")
    previous_questions = _ordered_questions(db, previous.id)
    if len(previous_questions) != 1:
        raise HTTPException(
            status_code=409,
            detail="This legacy endpoint supports one-question assessments only. Create a full reviewed version instead.",
        )
    rubric = [criterion.model_dump() for criterion in payload.rubric]
    question = previous_questions[0]
    question_data = _question_payload(question)
    question_data["rubric"] = rubric
    question_data["max_marks"] = sum(float(item["max_marks"]) for item in rubric)
    version = create_draft_version(
        db,
        assessment,
        title=previous.title,
        subject=previous.subject,
        language=previous.language,
        questions=[question_data],
    )
    try:
        lock_version(db, assessment, version)
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error)) from error
    db.commit()
    return {"rubric_version": version.version_number, "regraded": [], "version_id": version.id}


@app.get("/api/compare/{assessment_id}")
def compare_scores(assessment_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    if db.query(Assessment.id).filter(Assessment.id == assessment_id).first() is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    pairs = _build_comparison_rows(db, assessment_id)
    normalized_errors = [row["difference_percentage_points"] for row in pairs]
    ai_scores = [row["ai_percentage"] for row in pairs]
    teacher_scores = [row["teacher_percentage"] for row in pairs]
    return {
        "assessment_id": assessment_id,
        "paired_question_answers": len(pairs),
        "mae_percentage_points": round(sum(normalized_errors) / len(normalized_errors), 4) if pairs else None,
        "qwk": calculate_qwk(ai_scores, teacher_scores),
        "pairs": pairs,
    }


@app.get("/api/comparisons")
def list_comparisons(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    return _build_comparison_rows(db)


def _build_comparison_rows(db: Session, assessment_id: Optional[int] = None) -> List[Dict[str, Any]]:
    query = (
        db.query(QuestionAnswer)
        .join(Submission, Submission.id == QuestionAnswer.submission_id)
        .join(SubmissionReference, SubmissionReference.submission_id == Submission.id)
        .join(AssessmentVersion, AssessmentVersion.id == SubmissionReference.version_id)
        .join(AssessmentQuestion, AssessmentQuestion.id == QuestionAnswer.question_id)
        .join(Assessment, Assessment.id == Submission.assessment_id)
        .filter(
            AssessmentVersion.status == "locked",
            QuestionAnswer.teacher_score.isnot(None),
            QuestionAnswer.maximum_score > 0,
            QuestionAnswer.teacher_score >= 0,
            QuestionAnswer.teacher_score <= QuestionAnswer.maximum_score,
        )
    )
    if assessment_id is not None:
        query = query.filter(Submission.assessment_id == assessment_id)
    answers = query.order_by(QuestionAnswer.created_at.desc()).all()
    result = []
    for answer in answers:
        submission = answer.submission
        reference = submission.reference
        version = reference.version
        question = answer.question
        maximum = float(answer.maximum_score)
        ai_score = float(answer.ai_score)
        teacher_score = float(answer.teacher_score)
        difference = abs(ai_score - teacher_score)
        tolerance = max(2.0, 0.2 * maximum)
        ai_percentage = ai_score / maximum * 100
        teacher_percentage = teacher_score / maximum * 100
        difference_points = abs(ai_percentage - teacher_percentage)
        status = (
            "Exact agreement"
            if difference <= 0.01
            else "Partial agreement"
            if difference <= tolerance
            else "Disagreement"
        )
        result.append(
            {
                "id": answer.id,
                "assessment_id": submission.assessment_id,
                "assessment_title": version.title,
                "subject": version.subject,
                "version_id": version.id,
                "version_number": version.version_number,
                "student_id": submission.student_id,
                "attempt_number": reference.attempt_number,
                "question_id": question.question_key,
                "question": question.question_text,
                "created_at": answer.created_at.isoformat() if answer.created_at else "",
                "ai_score": ai_score,
                "teacher_score": teacher_score,
                "maximum_score": maximum,
                "ai_percentage": ai_percentage,
                "teacher_percentage": teacher_percentage,
                "difference": difference,
                "difference_percentage_points": difference_points,
                "tolerance": tolerance,
                "status": status,
                "metric_label": "AI-teacher agreement",
                "independent_reference_available": False,
            }
        )
    return result
