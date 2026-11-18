import { useEffect, useMemo, useState } from 'react';
import type { ChangeEvent } from 'react';
import { Download, FileSpreadsheet, Upload } from 'lucide-react';
import { PageIntro } from './PageIntro';
import { ResultsTable } from './ResultsTable';
import type { Assessment, CSVPreview, QuestionAnswerRow, ResultRow } from './types';

type GradingPageProps = {
  mode: 'ai' | 'teacher';
  assessments: Assessment[];
  selectedAssessmentId: number | null;
  onSelectAssessment: (id: number) => void;
  onCsvUpload: (file: File, versionId: number) => void;
  onImportCsv: (startNewAttempt: boolean, versionId: number) => void;
  csvPreview: CSVPreview | null;
  onClearCsvPreview: () => void;
  results: ResultRow[];
  questionAnswers: QuestionAnswerRow[];
  onSaveTeacherMark: (questionAnswerId: number, score: number, notes: string) => void;
  onExportBatch: (batchId: number) => void;
};

type TeacherEdit = {
  score: string;
  notes: string;
};

export function GradingPage({
  mode,
  assessments,
  selectedAssessmentId,
  onSelectAssessment,
  onCsvUpload,
  onImportCsv,
  csvPreview,
  onClearCsvPreview,
  results,
  questionAnswers,
  onSaveTeacherMark,
  onExportBatch,
}: GradingPageProps) {
  const isTeacher = mode === 'teacher';
  const lockedAssessments = assessments.filter((assessment) => assessment.is_locked && assessment.version_id);
  const [startNewAttempt, setStartNewAttempt] = useState(false);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);
  const [teacherEdits, setTeacherEdits] = useState<Record<number, TeacherEdit>>({});
  const selectedAssessment = assessments.find((assessment) => assessment.id === selectedAssessmentId);
  const lockedVersions = selectedAssessment?.version_history.filter((version) => version.status === 'locked') ?? [];
  const visibleAnswers = useMemo(
    () => questionAnswers.filter((answer) => answer.version_id === selectedVersionId),
    [questionAnswers, selectedVersionId],
  );
  const visibleResults = useMemo(
    () => results.filter((result) => result.version_id === selectedVersionId),
    [results, selectedVersionId],
  );
  const exportBatches = useMemo(
    () => [...new Set(visibleAnswers.map((answer) => answer.batch_id).filter((id): id is number => id !== null))],
    [visibleAnswers],
  );

  useEffect(() => {
    setSelectedVersionId(selectedAssessment?.version_id ?? null);
    setStartNewAttempt(false);
  }, [selectedAssessment?.id, selectedAssessment?.version_id]);

  useEffect(() => {
    setTeacherEdits(Object.fromEntries(
      visibleAnswers.map((answer) => [
        answer.id,
        { score: answer.teacher_score === null ? '' : String(answer.teacher_score), notes: answer.teacher_notes },
      ]),
    ));
  }, [visibleAnswers]);

  const updateTeacherEdit = (id: number, field: keyof TeacherEdit, value: string) => {
    setTeacherEdits((current) => ({
      ...current,
      [id]: { ...(current[id] ?? { score: '', notes: '' }), [field]: value },
    }));
  };

  const handleFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file && selectedVersionId !== null) {
      setStartNewAttempt(false);
      onCsvUpload(file, selectedVersionId);
    }
    event.target.value = '';
  };

  const handleVersionChange = (versionId: number) => {
    setSelectedVersionId(versionId);
    setStartNewAttempt(false);
    onClearCsvPreview();
  };

  return (
    <>
      <PageIntro
        eyebrow={isTeacher ? 'Teacher scoring workspace' : 'Local AI scoring workspace'}
        title={isTeacher ? 'Enter teacher marks question by question.' : 'Grade student answers from CSV.'}
        description={
          isTeacher
            ? 'Teacher scores are entered independently for each student answer and saved without rerunning or overwriting AI grading.'
            : 'Upload a UTF-8 CSV with student_id, question_id, and student_answer. AI grading runs locally against the selected locked reference.'
        }
      />

      <section className="panel">
        <div className="section-header">
          <div><p className="eyebrow">Locked reference</p><h2>{isTeacher ? 'Choose work to score' : 'Choose an assessment'}</h2></div>
          <label className="field assessment-select">
            <span>Assessment</span>
            <select
              value={lockedAssessments.some((assessment) => assessment.id === selectedAssessmentId) ? selectedAssessmentId ?? '' : ''}
              onChange={(event) => {
                if (event.target.value) onSelectAssessment(Number(event.target.value));
              }}
            >
              <option value="">Choose locked assessment</option>
              {lockedAssessments.map((assessment) => (
                <option key={assessment.id} value={assessment.id}>
                  {assessment.title} · v{assessment.rubric_version}
                </option>
              ))}
            </select>
          </label>
        </div>
        {selectedAssessment && lockedVersions.length > 1 && (
          <label className="field assessment-version-select">
            <span>Reference version</span>
            <select
              value={selectedVersionId ?? ''}
              onChange={(event) => handleVersionChange(Number(event.target.value))}
            >
              {lockedVersions.map((version) => (
                <option key={version.id} value={version.id}>Version {version.version_number}</option>
              ))}
            </select>
          </label>
        )}
        {lockedAssessments.length === 0 ? (
          <div className="empty-state">Upload, review, and lock an assessment reference before grading.</div>
        ) : selectedAssessment && !selectedAssessment.is_locked ? (
          <div className="empty-state">Select a locked assessment reference to continue.</div>
        ) : null}
      </section>

      {!isTeacher && selectedAssessment?.is_locked && (
        <section className="panel">
          <div className="section-header">
            <div><p className="eyebrow">Student answers</p><h2>Preview CSV before AI grading</h2></div>
            <FileSpreadsheet size={20} className="muted-icon" />
          </div>
          <label className="upload-box upload-label">
            <Upload size={19} />
            <span>Choose a CSV file to preview</span>
            <small>UTF-8 · one row per student answer · up to 15 MB</small>
            <input type="file" accept=".csv,text/csv" className="hidden-input" onChange={handleFile} />
          </label>
          <p className="helper-copy">Required columns: student_id, question_id, student_answer. For a single-question assessment, question_id may be omitted. Teacher-score columns are rejected.</p>
          {csvPreview && (
            <div className="csv-preview">
              <div className="preview-title">
                {csvPreview.filename} · {csvPreview.rows.length} answer rows
                <button type="button" className="text-link" onClick={onClearCsvPreview}>Clear preview</button>
              </div>
              {csvPreview.errors.length > 0 && (
                <div className="error-box" role="alert">
                  {csvPreview.errors.map((error, index) => (
                    <div key={`${error.row}-${index}`}>Row {error.row}: {error.error}</div>
                  ))}
                </div>
              )}
              {csvPreview.requires_new_attempt && (
                <div className="notice-callout" role="status">
                  This file or some student/question answers already exist. Choose the explicit new-attempt option to preserve both sets without overwriting.
                </div>
              )}
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Student</th><th>Question</th><th>Answer</th></tr></thead>
                  <tbody>
                    {csvPreview.rows.slice(0, 8).map((row, index) => (
                      <tr key={`${row.student_id}-${row.question_id}-${index}`}>
                        <td>{row.student_id}</td>
                        <td>{row.question_id}</td>
                        <td className="answer-cell">{row.student_answer.substring(0, 100)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <label className="checkbox-field">
                <input type="checkbox" checked={startNewAttempt} onChange={(event) => setStartNewAttempt(event.target.checked)} />
                <span>Import as a new attempt when any student/question record already exists</span>
              </label>
              <button
                type="button"
                className="primary-button full-width"
                disabled={!csvPreview.rows.length || csvPreview.errors.length > 0 || (csvPreview.requires_new_attempt && !startNewAttempt)}
                onClick={() => selectedVersionId !== null && onImportCsv(startNewAttempt, selectedVersionId)}
              >
                Grade and import CSV
              </button>
            </div>
          )}
        </section>
      )}

      {isTeacher && selectedAssessment?.is_locked && (
        <section className="panel">
          <div className="section-header">
            <div><p className="eyebrow">Teacher-only workflow</p><h2>Question-level marks</h2></div>
            {exportBatches.length > 0 && (
              <div className="export-batch-actions">
                {exportBatches.map((batchId) => (
                  <button type="button" className="secondary-button button-compact" key={batchId} onClick={() => onExportBatch(batchId)}>
                    <Download size={15} /> Export batch {batchId}
                  </button>
                ))}
              </div>
            )}
          </div>
          {visibleAnswers.length === 0 ? (
            <div className="empty-state">No student answers exist for this assessment version. Upload a student-answer CSV on the AI Grading page first.</div>
          ) : (
            <div className="table-wrap wide">
              <table className="teacher-marks-table">
                <thead>
                  <tr><th>Student / attempt</th><th>Question</th><th>Student answer</th><th>AI score</th><th>Teacher mark</th><th>Teacher notes</th><th>Action</th></tr>
                </thead>
                <tbody>
                  {visibleAnswers.map((answer) => {
                    const edit = teacherEdits[answer.id] ?? { score: '', notes: '' };
                    return (
                      <tr key={answer.id}>
                        <td>{answer.student_id}<small>Attempt {answer.attempt_number}</small></td>
                        <td><strong>{answer.question_id}</strong><small>{answer.question}</small></td>
                        <td className="answer-cell">{answer.student_answer}</td>
                        <td>{answer.ai_score}/{answer.maximum_score}</td>
                        <td>
                          <label className="sr-only" htmlFor={`teacher-score-${answer.id}`}>Teacher score</label>
                          <input
                            id={`teacher-score-${answer.id}`}
                            type="number"
                            min="0"
                            max={answer.maximum_score}
                            step="any"
                            value={edit.score}
                            onChange={(event) => updateTeacherEdit(answer.id, 'score', event.target.value)}
                          />
                        </td>
                        <td>
                          <label className="sr-only" htmlFor={`teacher-notes-${answer.id}`}>Teacher notes</label>
                          <textarea
                            id={`teacher-notes-${answer.id}`}
                            value={edit.notes}
                            onChange={(event) => updateTeacherEdit(answer.id, 'notes', event.target.value)}
                            rows={2}
                          />
                        </td>
                        <td>
                          <button
                            type="button"
                            className="secondary-button button-compact"
                            disabled={edit.score === '' || Number(edit.score) < 0 || Number(edit.score) > answer.maximum_score}
                            onClick={() => onSaveTeacherMark(answer.id, Number(edit.score), edit.notes)}
                          >
                            Save mark
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          <p className="helper-copy">Teacher marks are independent references, not verified accuracy. The CSV export retains all source columns and adds question_id and teacher_score.</p>
        </section>
      )}

      <section className="panel">
        <div className="section-header">
          <div><p className="eyebrow">Assessment results</p><h2>Recent student attempts</h2></div>
          {selectedAssessmentId && <span className="assessment-chip">{visibleResults.length} attempts</span>}
        </div>
        {selectedAssessmentId ? (
          <ResultsTable
            assessments={assessments.filter((assessment) => assessment.id === selectedAssessmentId)}
            resultsByAssessment={{ [selectedAssessmentId]: visibleResults }}
          />
        ) : (
          <div className="empty-state">Select an assessment to review its submissions.</div>
        )}
      </section>
    </>
  );
}
