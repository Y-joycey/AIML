export type Language = 'English' | 'Kannada' | 'Hindi';

export type Criterion = {
  id: string;
  title: string;
  description: string;
  max_marks: number;
  partial_credit: string;
};

export type AssessmentQuestion = {
  question_id: string;
  question: string;
  model_answer: string;
  max_marks: number;
  rubric: Criterion[];
};

export type AssessmentVersionSummary = {
  id: number;
  version_number: number;
  status: string;
  source_filename: string | null;
  locked_at: string | null;
};

export type Assessment = {
  id: number;
  title: string;
  subject: string;
  language: string;
  question: string;
  model_answer: string;
  max_marks: number;
  rubric: Criterion[];
  rubric_version: number;
  version_id: number | null;
  question_count: number;
  questions: AssessmentQuestion[];
  reference_status: string;
  is_locked: boolean;
  source_filename: string | null;
  draft_version_id: number | null;
  version_history: AssessmentVersionSummary[];
  created_at: string;
};

export type AssessmentDraft = {
  id: number;
  version_number: number;
  title: string;
  subject: string;
  language: string;
  status: string;
  is_locked: boolean;
  source_filename: string | null;
  locked_at: string | null;
  questions: AssessmentQuestion[];
};

export type DashboardData = {
  total_assessments: number;
  total_students: number;
  average_marks: number;
  graded_submissions: number;
  pending_reviews: number;
  score_distribution: Record<string, number>;
  recent_activities: Array<{ title: string; time: string; status: string }>;
};

export type ResultRow = {
  id: number;
  student_id: string;
  student_answer: string;
  total_score: number;
  maximum_score: number;
  percentage: number;
  review_status: string;
  human_score: number | null;
  teacher_notes: string | null;
  criteria: Array<Record<string, unknown>>;
  feedback: { overall_feedback?: string };
  confidence: number;
  discordance: number;
  version_id: number | null;
  version_number: number | null;
  attempt_number: number | null;
  created_at: string;
};

export type CSVPreviewRow = {
  student_id: string;
  question_id: string;
  question: string;
  student_answer: string;
  source_columns: Record<string, string>;
};

export type CSVPreview = {
  rows: CSVPreviewRow[];
  errors: CSVError[];
  headers: string[];
  content_sha256: string;
  filename: string;
  version_id: number;
  duplicate_file: boolean;
  existing_answer_conflicts: Array<{ student_id: string; question_id: string }>;
  requires_new_attempt: boolean;
};

export type CSVError = {
  row: number;
  student_id?: string;
  error: string;
};

export type QuestionAnswerRow = {
  id: number;
  submission_id: number;
  student_id: string;
  attempt_number: number;
  batch_id: number | null;
  version_id: number;
  question_id: string;
  question: string;
  student_answer: string;
  ai_score: number;
  maximum_score: number;
  ai_criteria: Array<Record<string, unknown>>;
  ai_feedback: { overall_feedback?: string };
  ai_confidence: number;
  review_status: string;
  teacher_score: number | null;
  teacher_notes: string;
  created_at: string;
};

export type ComparisonRecord = {
  id: number;
  assessment_id: number;
  assessment_title: string;
  subject: string;
  version_id: number;
  version_number: number;
  student_id: string;
  attempt_number: number;
  question_id: string;
  question: string;
  created_at: string;
  ai_score: number;
  teacher_score: number;
  maximum_score: number;
  ai_percentage: number;
  teacher_percentage: number;
  difference: number;
  difference_percentage_points: number;
  tolerance: number;
  status: 'Exact agreement' | 'Partial agreement' | 'Disagreement';
  metric_label: 'AI-teacher agreement';
  independent_reference_available: false;
};

export type ComparisonRow = {
  id: string;
  assessmentId: number;
  assessmentTitle: string;
  subject: string;
  versionNumber: number;
  studentId: string;
  attemptNumber: number;
  questionId: string;
  question: string;
  createdAt: string;
  aiScore: number;
  teacherScore: number;
  maximumScore: number;
  aiPercentage: number;
  teacherPercentage: number;
  difference: number;
  differencePercentagePoints: number;
  tolerance: number;
  status: 'Exact agreement' | 'Partial agreement' | 'Disagreement';
};
