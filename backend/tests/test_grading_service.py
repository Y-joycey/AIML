from backend.app.services.grading_service import evaluate_question, evaluate_submission, validate_criterion_marks


def test_evaluate_submission_returns_valid_total():
    assessment = {
        "model_answer": "The character becomes more responsible and confident after learning from mistakes.",
        "rubric": [
            {"id": "C1", "title": "Concept", "description": "Shows understanding of change", "max_marks": 5},
            {"id": "C2", "title": "Evidence", "description": "Uses evidence from the text", "max_marks": 4},
            {"id": "C3", "title": "Clarity", "description": "Response is well structured", "max_marks": 3},
        ],
    }
    result = evaluate_submission(assessment, "The character learns from mistakes and becomes more confident and responsible.")
    assert result["total_score"] <= 12
    assert result["maximum_score"] == 12
    assert result["percentage"] >= 0


def test_invalid_criterion_marks_are_rejected():
    criteria = [
        {"criterion_id": "C1", "max_marks": 5, "awarded_marks": 6},
        {"criterion_id": "C2", "max_marks": 4, "awarded_marks": 2},
    ]
    try:
        validate_criterion_marks(criteria)
        assert False, "Expected ValueError for invalid marks"
    except ValueError:
        pass


def test_local_model_scores_cannot_exceed_question_rubric(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.grading_service.grade_question",
        lambda _question, _answer: {
            "criteria": [{"criterion_id": "C1", "awarded_marks": 6, "confidence": 0.9}],
            "overall_feedback": "Feedback",
        },
    )
    question = {"rubric": [{"id": "C1", "title": "Understanding", "max_marks": 5}]}

    try:
        evaluate_question(question, "A complete answer.")
        assert False, "Expected out-of-range model marks to be rejected"
    except ValueError as error:
        assert "out-of-range values" in str(error)
