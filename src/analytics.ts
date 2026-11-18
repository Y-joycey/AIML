import type { ComparisonRecord, ComparisonRow } from './types';

export function buildComparisonRows(rows: ComparisonRow[]): ComparisonRow[] {
  return rows;
}

export function normalizeComparisonRows(records: ComparisonRecord[]): ComparisonRow[] {
  return records.map((record) => ({
    id: `${record.version_id}-${record.id}`,
    assessmentId: record.assessment_id,
    assessmentTitle: record.assessment_title,
    subject: record.subject,
    versionNumber: record.version_number,
    studentId: record.student_id,
    attemptNumber: record.attempt_number,
    questionId: record.question_id,
    question: record.question,
    createdAt: record.created_at,
    aiScore: record.ai_score,
    teacherScore: record.teacher_score,
    maximumScore: record.maximum_score,
    aiPercentage: record.ai_percentage,
    teacherPercentage: record.teacher_percentage,
    difference: record.difference,
    differencePercentagePoints: record.difference_percentage_points,
    tolerance: record.tolerance,
    status: record.status,
  }));
}

export function percentage(value: number, denominator: number): number | null {
  return denominator > 0 ? (value / denominator) * 100 : null;
}

export function mean(values: number[]): number | null {
  return values.length ? values.reduce((total, value) => total + value, 0) / values.length : null;
}
