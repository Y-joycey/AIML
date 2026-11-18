from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from sklearn.metrics import cohen_kappa_score

from .ai_adapter import AIAdapter
from .local_model_service import grade_question


def validate_criterion_marks(criteria: List[Dict[str, Any]]) -> None:
    seen_ids = set()
    total = 0.0
    for criterion in criteria:
        criterion_id = str(criterion.get("criterion_id", "")).strip()
        if not criterion_id:
            raise ValueError("Each rubric criterion must include a non-empty criterion ID.")
        if criterion_id in seen_ids:
            raise ValueError(f"Duplicate criterion ID found: {criterion_id}")
        seen_ids.add(criterion_id)
        max_marks = float(criterion.get("max_marks", 0) or 0)
        awarded = float(criterion.get("awarded_marks", 0) or 0)
        if awarded < 0 or awarded > max_marks:
            raise ValueError(f"Criterion {criterion_id} marks are invalid: awarded {awarded} exceeds max {max_marks}.")
        total += max_marks
    if total <= 0:
        raise ValueError("Assessment rubric must define at least one maximum mark.")


def compute_total(criteria: List[Dict[str, Any]]) -> float:
    return round(sum(float(item.get("awarded_marks", 0) or 0) for item in criteria), 2)


def calculate_percentage(score: float, maximum: float) -> float:
    if maximum <= 0:
        return 0.0
    return round((score / maximum) * 100, 2)


def build_total_from_criteria(criteria: List[Dict[str, Any]]) -> Tuple[float, float]:
    total = compute_total(criteria)
    maximum = sum(float(item.get("max_marks", 0) or 0) for item in criteria)
    return round(total, 2), round(maximum, 2)


def calculate_qwk(ai_scores: List[float], human_scores: List[float]) -> Optional[float]:
    if len(ai_scores) < 2 or len(ai_scores) != len(human_scores):
        return None
    pairs = [
        (ai, human)
        for ai, human in zip(ai_scores, human_scores)
        if math.isfinite(float(ai)) and math.isfinite(float(human))
    ]
    if len(pairs) < 2:
        return None
    observed = cohen_kappa_score(
        [round(ai) for ai, _ in pairs],
        [round(human) for _, human in pairs],
        weights="quadratic",
    )
    return None if math.isnan(float(observed)) else round(float(observed), 4)


def calculate_mae(ai_scores: List[float], human_scores: List[float]) -> Optional[float]:
    valid = [(a, h) for a, h in zip(ai_scores, human_scores) if a is not None and h is not None]
    if not valid:
        return None
    diffs = [abs(a - h) for a, h in valid]
    return round(sum(diffs) / len(diffs), 4)


def disagreement_threshold(maximum: float) -> float:
    return max(2.0, 0.2 * float(maximum or 0))


def evaluate_submission(assessment: Dict[str, Any], student_answer: str, human_score: Optional[float] = None, teacher_notes: Optional[str] = None, api_key: str = "") -> Dict[str, Any]:
    rubric = assessment.get("rubric", [])
    if not rubric:
        raise ValueError("Assessment requires at least one rubric criterion before grading.")

    ai_adapter = AIAdapter(provider="demo", api_key=api_key)
    criteria = []
    for criterion in rubric:
        result = ai_adapter.grade_criterion(criterion, student_answer, assessment.get("model_answer", ""))
        criteria.append({
            "criterion_id": result["criterion_id"],
            "criterion_title": result["criterion_title"],
            "awarded_marks": result["awarded_marks"],
            "max_marks": result["max_marks"],
            "rationale": result["rationale"],
            "evidence": result["evidence"],
            "confidence": result["confidence"],
            "needs_review": result["needs_review"],
        })

    validate_criterion_marks(criteria)
    total, maximum = build_total_from_criteria(criteria)
    percentage = calculate_percentage(total, maximum)
    feedback_payload = ai_adapter.build_feedback(rubric, student_answer, criteria)
    threshold = disagreement_threshold(maximum)

    disagreement = False
    if human_score is not None:
        disagreement = abs(float(human_score) - total) > threshold

    return {
        "total_score": total,
        "maximum_score": maximum,
        "percentage": percentage,
        "criteria": criteria,
        "feedback": feedback_payload,
        "review_status": "needs_review" if any(item["needs_review"] for item in criteria) else "approved",
        "confidence": round(sum(item["confidence"] for item in criteria) / len(criteria), 2),
        "human_score": human_score,
        "teacher_notes": teacher_notes,
        "disagreement_threshold": threshold,
        "disagreement": disagreement,
    }


def evaluate_question(question: Dict[str, Any], student_answer: str) -> Dict[str, Any]:
    rubric = question.get("rubric", [])
    if not rubric:
        raise ValueError("Question requires at least one rubric criterion before AI grading.")
    if not student_answer.strip():
        raise ValueError("A student answer is required before AI grading.")

    generated = grade_question(question, student_answer)
    generated_criteria = generated.get("criteria")
    expected = {str(item.get("id", "")).strip(): item for item in rubric}
    if not isinstance(generated_criteria, list) or not expected:
        raise ValueError("The local model returned no usable rubric scores.")

    scores_by_id: Dict[str, Dict[str, Any]] = {}
    for item in generated_criteria:
        if not isinstance(item, dict):
            raise ValueError("The local model returned a malformed rubric score.")
        criterion_id = str(item.get("criterion_id", "")).strip()
        if criterion_id not in expected or criterion_id in scores_by_id:
            raise ValueError("The local model returned an unknown or duplicate rubric criterion ID.")
        scores_by_id[criterion_id] = item
    if scores_by_id.keys() != expected.keys():
        raise ValueError("The local model did not score every rubric criterion.")

    criteria = []
    for criterion in rubric:
        criterion_id = str(criterion["id"]).strip()
        model_score = scores_by_id[criterion_id]
        try:
            awarded_marks = float(model_score["awarded_marks"])
            confidence = float(model_score["confidence"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"The local model returned invalid marks for criterion {criterion_id}.") from error
        max_marks = float(criterion["max_marks"])
        if awarded_marks < 0 or awarded_marks > max_marks or not 0 <= confidence <= 1:
            raise ValueError(f"The local model returned out-of-range values for criterion {criterion_id}.")
        criteria.append(
            {
                "criterion_id": criterion_id,
                "criterion_title": str(criterion.get("title") or ""),
                "awarded_marks": round(awarded_marks, 2),
                "max_marks": max_marks,
                "rationale": str(model_score.get("rationale") or ""),
                "evidence": str(model_score.get("evidence") or ""),
                "confidence": round(confidence, 2),
                "needs_review": confidence < 0.55,
            }
        )

    validate_criterion_marks(criteria)
    total, maximum = build_total_from_criteria(criteria)
    average_confidence = round(sum(item["confidence"] for item in criteria) / len(criteria), 2)
    return {
        "total_score": total,
        "maximum_score": maximum,
        "percentage": calculate_percentage(total, maximum),
        "criteria": criteria,
        "feedback": {
            "overall_feedback": str(generated.get("overall_feedback") or ""),
        },
        "review_status": "needs_review" if any(item["needs_review"] for item in criteria) else "approved",
        "confidence": average_confidence,
    }
