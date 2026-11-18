from typing import List, Optional, Any, Dict
from pydantic import BaseModel, ConfigDict, Field


class RubricCriterionInput(BaseModel):
    id: str
    title: str
    description: str
    max_marks: float = Field(ge=0)
    partial_credit: str = ""


class AssessmentInput(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    title: str
    subject: str
    language: str
    question: str
    model_answer: str
    rubric: List[RubricCriterionInput]


class SubmissionInput(BaseModel):
    assessment_id: int
    student_id: str
    student_answer: str
    human_score: Optional[float] = None
    teacher_notes: Optional[str] = None


class CSVRowPayload(BaseModel):
    student_id: str
    student_answer: str
    human_score: Optional[float] = None
    teacher_notes: Optional[str] = None


class GradeSingleSubmissionRequest(BaseModel):
    assessment_id: int
    student_id: str
    student_answer: str
    human_score: Optional[float] = None
    teacher_notes: Optional[str] = None


class RubricVersionUpdate(BaseModel):
    assessment_id: int
    rubric: List[RubricCriterionInput]


class AssessmentQuestionInput(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    question_id: str = Field(min_length=1, max_length=80)
    question: str = ""
    model_answer: str = ""
    max_marks: float = Field(default=0, ge=0)
    rubric: List[RubricCriterionInput] = Field(default_factory=list)


class AssessmentReviewInput(BaseModel):
    title: str
    subject: str
    language: str
    questions: List[AssessmentQuestionInput] = Field(min_length=1)


class TeacherMarkInput(BaseModel):
    score: float = Field(ge=0)
    notes: Optional[str] = None


class DashboardData(BaseModel):
    total_assessments: int
    total_students: int
    average_marks: float
    graded_submissions: int
    pending_reviews: int
    score_distribution: Dict[str, int]
    recent_activities: List[Dict[str, Any]]


class MetricPair(BaseModel):
    ai_score: float
    human_score: float
    absolute_difference: float
    disagreement: bool
    qwk: Optional[float] = None
    mae: Optional[float] = None
    threshold: float
