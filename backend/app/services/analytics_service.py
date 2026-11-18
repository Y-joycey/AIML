from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List


def build_dashboard(assessments: List[Dict[str, Any]], submissions: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_assessments = len(assessments)
    unique_students = {item["student_id"] for item in submissions}
    total_students = len(unique_students)
    scores = [float(item.get("total_score", 0) or 0) for item in submissions]
    average_marks = round(sum(scores) / len(scores), 2) if scores else 0.0
    graded_submissions = len(submissions)
    pending_reviews = sum(1 for item in submissions if item.get("review_status") == "needs_review")
    score_distribution = {
        "0-25": 0,
        "26-50": 0,
        "51-75": 0,
        "76-100": 0,
    }
    for item in submissions:
        percentage = float(item.get("percentage", 0) or 0)
        if percentage <= 25:
            score_distribution["0-25"] += 1
        elif percentage <= 50:
            score_distribution["26-50"] += 1
        elif percentage <= 75:
            score_distribution["51-75"] += 1
        else:
            score_distribution["76-100"] += 1

    recent_activities = [
        {
            "title": f"{item.get('student_id', 'Student')} graded for {item.get('assessment_title', 'assessment')}",
            "time": item.get("created_at", "Today"),
            "status": item.get("review_status", "approved"),
        }
        for item in submissions[:5]
    ]

    return {
        "total_assessments": total_assessments,
        "total_students": total_students,
        "average_marks": average_marks,
        "graded_submissions": graded_submissions,
        "pending_reviews": pending_reviews,
        "score_distribution": score_distribution,
        "recent_activities": recent_activities,
    }
