import pytest

from backend.app.models import AssessmentQuestion, AssessmentVersion
from backend.app.services.csv_service import CSVValidationError, parse_student_csv


def build_version(question_keys: list[str]) -> AssessmentVersion:
    return AssessmentVersion(
        id=1,
        assessment_id=1,
        version_number=1,
        status="locked",
        questions=[
            AssessmentQuestion(
                id=index,
                version_id=1,
                question_key=question_key,
                question_text=f"Question {question_key}",
                max_marks=5,
                display_order=index,
                rubric_json=[],
            )
            for index, question_key in enumerate(question_keys, start=1)
        ],
    )


def test_parse_student_csv_preserves_source_columns_for_each_question():
    version = build_version(["Q1", "Q2"])

    headers, rows, errors = parse_student_csv(
        b"student_id,question_id,student_answer,section\nS-1,Q2,Answer two,A\n",
        version,
    )

    assert headers == ["student_id", "question_id", "student_answer", "section"]
    assert errors == []
    assert rows[0]["question_key"] == "Q2"
    assert rows[0]["source_row"]["section"] == "A"


def test_parse_student_csv_requires_question_id_for_multiple_questions():
    with pytest.raises(CSVValidationError, match="require a question_id column"):
        parse_student_csv(b"student_id,student_answer\nS-1,Answer\n", build_version(["Q1", "Q2"]))


def test_parse_student_csv_rejects_teacher_scores():
    with pytest.raises(CSVValidationError, match="cannot contain teacher score columns"):
        parse_student_csv(
            b"student_id,question_id,student_answer,teacher_score\nS-1,Q1,Answer,4\n",
            build_version(["Q1"]),
        )


def test_parse_student_csv_reports_duplicate_student_question_rows():
    _, rows, errors = parse_student_csv(
        b"student_id,question_id,student_answer\nS-1,Q1,First\nS-1,Q1,Second\n",
        build_version(["Q1"]),
    )

    assert len(rows) == 1
    assert errors == [
        {
            "row": 3,
            "student_id": "S-1",
            "error": "Duplicate answer for question Q1 in this CSV.",
        }
    ]
