from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from .database import Base


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=False)
    language = Column(String(50), nullable=False)
    question = Column(Text, nullable=False)
    model_answer = Column(Text, nullable=False)
    max_marks = Column(Float, default=0)
    rubric_version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    rubric_json = Column(JSON, default=list)

    submissions = relationship("Submission", back_populates="assessment")
    versions = relationship("AssessmentVersion", back_populates="assessment")


class AssessmentVersion(Base):
    __tablename__ = "assessment_versions"
    __table_args__ = (
        UniqueConstraint("assessment_id", "version_number", name="uq_assessment_version_number"),
    )

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False, default="")
    subject = Column(String(255), nullable=False, default="")
    language = Column(String(50), nullable=False, default="English")
    source_filename = Column(String(255), nullable=True)
    source_sha256 = Column(String(64), nullable=True)
    source_path = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)
    locked_at = Column(DateTime, nullable=True)

    assessment = relationship("Assessment", back_populates="versions")
    questions = relationship("AssessmentQuestion", back_populates="version", cascade="all, delete-orphan")


class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"
    __table_args__ = (
        UniqueConstraint("version_id", "question_key", name="uq_version_question_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey("assessment_versions.id"), nullable=False, index=True)
    question_key = Column(String(80), nullable=False)
    question_text = Column(Text, nullable=False, default="")
    model_answer = Column(Text, nullable=False, default="")
    max_marks = Column(Float, nullable=False, default=0)
    rubric_json = Column(JSON, nullable=False, default=list)
    display_order = Column(Integer, nullable=False, default=0)

    version = relationship("AssessmentVersion", back_populates="questions")
    answers = relationship("QuestionAnswer", back_populates="question")


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(120), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CSVImportBatch(Base):
    __tablename__ = "csv_import_batches"

    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey("assessment_versions.id"), nullable=False, index=True)
    source_filename = Column(String(255), nullable=False)
    content_sha256 = Column(String(64), nullable=False, index=True)
    headers_json = Column(JSON, nullable=False, default=list)
    is_new_attempt = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    version = relationship("AssessmentVersion")


class SubmissionReference(Base):
    __tablename__ = "submission_references"

    submission_id = Column(Integer, ForeignKey("submissions.id"), primary_key=True)
    version_id = Column(Integer, ForeignKey("assessment_versions.id"), nullable=False, index=True)
    student_pk = Column(Integer, ForeignKey("students.id"), nullable=True, index=True)
    import_batch_id = Column(Integer, ForeignKey("csv_import_batches.id"), nullable=True, index=True)
    attempt_number = Column(Integer, nullable=False, default=1)
    is_legacy = Column(Boolean, nullable=False, default=False)

    submission = relationship("Submission", back_populates="reference")
    version = relationship("AssessmentVersion")
    student = relationship("Student")
    import_batch = relationship("CSVImportBatch")


class QuestionAnswer(Base):
    __tablename__ = "question_answers"
    __table_args__ = (
        UniqueConstraint("submission_id", "question_id", name="uq_submission_question_answer"),
    )

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("assessment_questions.id"), nullable=False, index=True)
    student_answer = Column(Text, nullable=False)
    ai_score = Column(Float, nullable=False)
    maximum_score = Column(Float, nullable=False)
    ai_criteria_json = Column(JSON, nullable=False, default=list)
    ai_feedback_json = Column(JSON, nullable=False, default=dict)
    ai_confidence = Column(Float, nullable=False, default=0)
    review_status = Column(String(50), nullable=False, default="needs_review")
    teacher_score = Column(Float, nullable=True)
    teacher_notes = Column(Text, nullable=True)
    source_row_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    submission = relationship("Submission")
    question = relationship("AssessmentQuestion", back_populates="answers")


class LegacyReview(Base):
    __tablename__ = "legacy_review"
    __table_args__ = (
        UniqueConstraint("record_type", "record_id", name="uq_legacy_review_record"),
    )

    id = Column(Integer, primary_key=True, index=True)
    record_type = Column(String(30), nullable=False)
    record_id = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default="needs_review")
    created_at = Column(DateTime, default=datetime.utcnow)


class SchemaMigration(Base):
    __tablename__ = "schema_migrations"

    version = Column(String(80), primary_key=True)
    applied_at = Column(DateTime, default=datetime.utcnow)


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id"), nullable=False)
    student_id = Column(String(120), nullable=False)
    student_answer = Column(Text, nullable=False)
    human_score = Column(Float, nullable=True)
    teacher_notes = Column(Text, nullable=True)
    total_score = Column(Float, default=0)
    maximum_score = Column(Float, default=0)
    percentage = Column(Float, default=0)
    review_status = Column(String(50), default="pending")
    feedback = Column(Text, default="")
    criteria_json = Column(JSON, default=list)
    ai_confidence = Column(Float, default=0)
    discordance = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    assessment = relationship("Assessment", back_populates="submissions")
    reference = relationship("SubmissionReference", back_populates="submission", uselist=False)
