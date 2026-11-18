import type { Assessment, ResultRow } from './types';

type ResultsTableProps = {
  assessments: Assessment[];
  resultsByAssessment: Record<number, ResultRow[]>;
  emptyMessage?: string;
};

export function ResultsTable({
  assessments,
  resultsByAssessment,
  emptyMessage = 'No graded submissions are available yet.',
}: ResultsTableProps) {
  const rows = assessments.flatMap((assessment) =>
    (resultsByAssessment[assessment.id] ?? []).map((result) => ({ assessment, result })),
  );

  if (!rows.length) {
    return <div className="empty-state">{emptyMessage}</div>;
  }

  return (
    <div className="table-wrap wide">
      <table>
        <thead>
          <tr>
            <th>Student / attempt</th>
            <th>Assessment</th>
            <th>Reference version</th>
            <th>AI score</th>
            <th>Percentage</th>
            <th>Teacher score</th>
            <th>Review status</th>
            <th>Feedback</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ assessment, result }) => (
            <tr key={`${assessment.id}-${result.id}`}>
              <td className="student-name">{result.student_id}<small>{result.attempt_number ? `Attempt ${result.attempt_number}` : 'Legacy record'}</small></td>
              <td>{assessment.title}</td>
              <td>{result.version_number ? `v${result.version_number}` : 'Legacy'}</td>
              <td>{result.total_score}/{result.maximum_score}</td>
              <td>{Number(result.percentage).toFixed(1)}%</td>
              <td>{result.human_score ?? '-'}</td>
              <td>
                <span className={`status-pill ${result.review_status === 'approved' ? 'success' : 'warning'}`}>
                  {result.review_status}
                </span>
              </td>
              <td className="feedback-cell">{result.feedback?.overall_feedback || 'No feedback generated'}</td>
              <td>{new Date(result.created_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
