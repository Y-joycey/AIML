import { useEffect, useMemo, useState } from 'react';
import type { ChangeEvent } from 'react';
import { FileUp, Plus, Save, ShieldCheck, Trash2 } from 'lucide-react';
import { PageIntro } from './PageIntro';
import type {
  Assessment,
  AssessmentDraft,
  AssessmentQuestion,
  Criterion,
  Language,
} from './types';

type AssessmentUploadMetadata = {
  title: string;
  subject: string;
  language: string;
  assessment_id?: number;
};

type AssessmentsPageProps = {
  assessments: Assessment[];
  selectedAssessmentId: number | null;
  assessmentDraft: AssessmentDraft | null;
  onUploadDocument: (file: File, metadata: AssessmentUploadMetadata) => void;
  onLoadDraft: (assessmentId: number, versionId: number) => void;
  onSaveDraft: (draft: AssessmentDraft) => void;
  onLockDraft: (draft: AssessmentDraft) => void;
  onSelectAssessment: (id: number) => void;
};

const emptyCriterion = (index: number): Criterion => ({
  id: `C${index + 1}`,
  title: '',
  description: '',
  max_marks: 1,
  partial_credit: '',
});

const emptyQuestion = (index: number): AssessmentQuestion => ({
  question_id: `Q${index + 1}`,
  question: '',
  model_answer: '',
  max_marks: 1,
  rubric: [emptyCriterion(0)],
});

export function AssessmentsPage({
  assessments,
  selectedAssessmentId,
  assessmentDraft,
  onUploadDocument,
  onLoadDraft,
  onSaveDraft,
  onLockDraft,
  onSelectAssessment,
}: AssessmentsPageProps) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [subject, setSubject] = useState('');
  const [language, setLanguage] = useState<Language>('English');
  const [targetAssessmentId, setTargetAssessmentId] = useState('');
  const [draft, setDraft] = useState<AssessmentDraft | null>(assessmentDraft);
  const lockedAssessments = assessments.filter((assessment) => assessment.is_locked);
  const totalMarks = useMemo(
    () => draft?.questions.reduce((sum, question) => sum + Number(question.max_marks || 0), 0) ?? 0,
    [draft],
  );

  useEffect(() => {
    setDraft(assessmentDraft);
    if (assessmentDraft) {
      setTitle(assessmentDraft.title);
      setSubject(assessmentDraft.subject);
      setLanguage((assessmentDraft.language || 'English') as Language);
    }
  }, [assessmentDraft]);

  const handleUpload = (event: ChangeEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) return;
    onUploadDocument(file, {
      title,
      subject,
      language,
      ...(targetAssessmentId ? { assessment_id: Number(targetAssessmentId) } : {}),
    });
  };

  const updateQuestion = (index: number, field: keyof AssessmentQuestion, value: string | number) => {
    setDraft((current) => current && ({
      ...current,
      questions: current.questions.map((question, itemIndex) =>
        itemIndex === index ? { ...question, [field]: value } : question,
      ),
    }));
  };

  const updateCriterion = (
    questionIndex: number,
    criterionIndex: number,
    field: keyof Criterion,
    value: string | number,
  ) => {
    setDraft((current) => current && ({
      ...current,
      questions: current.questions.map((question, index) => {
        if (index !== questionIndex) return question;
        const rubric = question.rubric.map((criterion, itemIndex) => {
          if (itemIndex !== criterionIndex) return criterion;
          return field === 'max_marks'
            ? { ...criterion, max_marks: Number(value) }
            : { ...criterion, [field]: String(value) };
        });
        return {
          ...question,
          rubric,
          ...(field === 'max_marks'
            ? { max_marks: rubric.reduce((sum, criterion) => sum + Number(criterion.max_marks || 0), 0) }
            : {}),
        };
      }),
    }));
  };

  const addQuestion = () => {
    setDraft((current) => current && ({
      ...current,
      questions: [...current.questions, emptyQuestion(current.questions.length)],
    }));
  };

  const removeQuestion = (index: number) => {
    setDraft((current) => current && ({
      ...current,
      questions: current.questions.filter((_, itemIndex) => itemIndex !== index),
    }));
  };

  const addCriterion = (questionIndex: number) => {
    setDraft((current) => current && ({
      ...current,
      questions: current.questions.map((question, index) =>
        index === questionIndex
          ? {
              ...question,
              rubric: [...question.rubric, emptyCriterion(question.rubric.length)],
              max_marks: question.max_marks + 1,
            }
          : question,
      ),
    }));
  };

  const removeCriterion = (questionIndex: number, criterionIndex: number) => {
    setDraft((current) => current && ({
      ...current,
      questions: current.questions.map((question, index) => {
        if (index !== questionIndex) return question;
        const rubric = question.rubric.filter((_, itemIndex) => itemIndex !== criterionIndex);
        return {
          ...question,
          rubric,
          max_marks: rubric.reduce((sum, criterion) => sum + Number(criterion.max_marks || 0), 0),
        };
      }),
    }));
  };

  return (
    <>
      <PageIntro
        eyebrow="Assessment workspace"
        title="Review source documents before grading."
        description="Upload a marking document, verify the extracted questions and references, then lock an immutable version for student submissions."
      />

      <div className="notice-callout">
        Documents are processed on this machine. Scanned PDFs and JPG/JPEG files require local Tesseract OCR; question extraction uses the local Ollama model. No document or student answer is sent to a cloud service.
      </div>

      <div className="page-grid page-grid-aside">
        <section className="panel">
          <div className="section-header compact">
            <div><p className="eyebrow">Source document</p><h2>Upload an assessment</h2></div>
          </div>
          <form className="form-stack" onSubmit={handleUpload}>
            <div className="field-grid two-up">
              <label className="field">
                <span>Assessment title (optional)</span>
                <input value={title} onChange={(event) => setTitle(event.target.value)} />
              </label>
              <label className="field">
                <span>Subject (optional)</span>
                <input value={subject} onChange={(event) => setSubject(event.target.value)} />
              </label>
              <label className="field">
                <span>Language</span>
                <select value={language} onChange={(event) => setLanguage(event.target.value as Language)}>
                  <option value="English">English</option>
                  <option value="Kannada">Kannada</option>
                  <option value="Hindi">Hindi</option>
                </select>
              </label>
              <label className="field">
                <span>Add as a new version (optional)</span>
                <select value={targetAssessmentId} onChange={(event) => setTargetAssessmentId(event.target.value)}>
                  <option value="">Create a new assessment</option>
                  {lockedAssessments.map((assessment) => (
                    <option key={assessment.id} value={assessment.id}>{assessment.title} · v{assessment.rubric_version}</option>
                  ))}
                </select>
              </label>
            </div>
            <label className="upload-box document-upload">
              <FileUp size={21} />
              <span>{file ? file.name : 'Choose PDF, JPG, or JPEG'}</span>
              <small>Maximum file size: 15 MB</small>
              <input
                type="file"
                accept=".pdf,.jpg,.jpeg,application/pdf,image/jpeg"
                className="hidden-input"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </label>
            <button type="submit" className="primary-button" disabled={!file}>
              <FileUp size={16} /> Extract and review
            </button>
          </form>
        </section>

        <aside className="panel">
          <div className="section-header compact">
            <div><p className="eyebrow">Assessment library</p><h2>Saved references</h2></div>
            <span className="count-chip">{assessments.length}</span>
          </div>
          {assessments.length ? (
            <div className="assessment-list">
              {assessments.map((assessment) => (
                <article key={assessment.id} className={`assessment-list-item ${assessment.id === selectedAssessmentId ? 'selected' : ''}`}>
                  <button type="button" className="assessment-library-select" onClick={() => onSelectAssessment(assessment.id)}>
                    <span className="assessment-list-icon">A</span>
                    <span className="assessment-list-copy">
                      <strong>{assessment.title || `Assessment ${assessment.id}`}</strong>
                      <small>{assessment.subject || 'Subject requires review'} · {assessment.question_count} question(s)</small>
                      <small>{assessment.is_locked ? `Locked v${assessment.rubric_version}` : assessment.reference_status}</small>
                    </span>
                  </button>
                  {assessment.draft_version_id && (
                    <button
                      type="button"
                      className="text-link"
                      onClick={() => onLoadDraft(assessment.id, assessment.draft_version_id!)}
                    >
                      Resume v{assessment.version_history.find((version) => version.id === assessment.draft_version_id)?.version_number ?? ''}
                    </button>
                  )}
                  {assessment.id === selectedAssessmentId && <span className="selected-indicator">Selected</span>}
                </article>
              ))}
            </div>
          ) : (
            <div className="empty-state small">Uploaded and locked assessments will appear here.</div>
          )}
          <p className="helper-copy">Previously locked versions remain attached to their grading records.</p>
        </aside>
      </div>

      {draft && (
        <section className="panel assessment-review-panel">
          <div className="section-header">
            <div>
              <p className="eyebrow">Version {draft.version_number} · {draft.source_filename || 'Legacy reference'}</p>
              <h2>Review extracted assessment content</h2>
              <p className="panel-subtitle">Check every extracted field. Incomplete answers or rubrics cannot be locked.</p>
            </div>
            <span className="status-pill warning">Draft · not available for grading</span>
          </div>

          <div className="field-grid three-up">
            <label className="field"><span>Assessment title</span><input value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
            <label className="field"><span>Subject</span><input value={draft.subject} onChange={(event) => setDraft({ ...draft, subject: event.target.value })} /></label>
            <label className="field">
              <span>Language</span>
              <select value={draft.language} onChange={(event) => setDraft({ ...draft, language: event.target.value })}>
                <option value="English">English</option><option value="Kannada">Kannada</option><option value="Hindi">Hindi</option>
              </select>
            </label>
          </div>

          <div className="rubric-block question-review-list">
            {draft.questions.map((question, questionIndex) => (
              <article className="question-review-card" key={`${draft.id}-${question.question_id}-${questionIndex}`}>
                <div className="rubric-title-row">
                  <div><p className="eyebrow">Question {questionIndex + 1}</p><h3>{question.question_id}</h3></div>
                  <button type="button" className="remove-button" onClick={() => removeQuestion(questionIndex)} aria-label={`Remove question ${question.question_id}`}>
                    <Trash2 size={15} /> Remove question
                  </button>
                </div>
                <div className="field-grid two-up">
                  <label className="field"><span>Stable question ID</span><input value={question.question_id} onChange={(event) => updateQuestion(questionIndex, 'question_id', event.target.value)} /></label>
                  <label className="field"><span>Maximum marks</span><input type="number" min="0" step="any" value={question.max_marks} onChange={(event) => updateQuestion(questionIndex, 'max_marks', Number(event.target.value))} /></label>
                </div>
                <label className="field"><span>Question prompt</span><textarea value={question.question} onChange={(event) => updateQuestion(questionIndex, 'question', event.target.value)} /></label>
                <label className="field"><span>Model answer</span><textarea value={question.model_answer} onChange={(event) => updateQuestion(questionIndex, 'model_answer', event.target.value)} /></label>
                <div className="rubric-block">
                  <div className="rubric-title-row">
                    <div><h3>Scoring criteria</h3><span className="helper-copy">Criteria maxima must sum to {question.max_marks} marks.</span></div>
                    <button type="button" className="secondary-button button-compact" onClick={() => addCriterion(questionIndex)}><Plus size={15} /> Add criterion</button>
                  </div>
                  {question.rubric.map((criterion, criterionIndex) => (
                    <div className="criterion-card" key={`${criterion.id}-${criterionIndex}`}>
                      <div className="criterion-grid">
                        <label className="sr-only" htmlFor={`criterion-id-${questionIndex}-${criterionIndex}`}>Criterion ID</label>
                        <input id={`criterion-id-${questionIndex}-${criterionIndex}`} value={criterion.id} onChange={(event) => updateCriterion(questionIndex, criterionIndex, 'id', event.target.value)} className="criterion-small" placeholder="C1" />
                        <label className="sr-only" htmlFor={`criterion-title-${questionIndex}-${criterionIndex}`}>Criterion title</label>
                        <input id={`criterion-title-${questionIndex}-${criterionIndex}`} value={criterion.title} onChange={(event) => updateCriterion(questionIndex, criterionIndex, 'title', event.target.value)} className="criterion-title" placeholder="Criterion title" />
                        <label className="sr-only" htmlFor={`criterion-marks-${questionIndex}-${criterionIndex}`}>Maximum marks</label>
                        <input
                          id={`criterion-marks-${questionIndex}-${criterionIndex}`}
                          type="number"
                          min="0"
                          step="any"
                          value={criterion.max_marks}
                          onChange={(event) => updateCriterion(questionIndex, criterionIndex, 'max_marks', Number(event.target.value))}
                          className="criterion-score"
                        />
                        <button type="button" className="remove-button" onClick={() => removeCriterion(questionIndex, criterionIndex)} aria-label={`Remove ${criterion.title || 'criterion'}`}>
                          <Trash2 size={15} /> Remove
                        </button>
                      </div>
                      <div className="criterion-text-stack">
                        <label className="field"><span>Criterion description</span><textarea value={criterion.description} onChange={(event) => updateCriterion(questionIndex, criterionIndex, 'description', event.target.value)} /></label>
                        <label className="field"><span>Partial-credit guidance</span><textarea value={criterion.partial_credit} onChange={(event) => updateCriterion(questionIndex, criterionIndex, 'partial_credit', event.target.value)} /></label>
                      </div>
                    </div>
                  ))}
                </div>
              </article>
            ))}
            <button type="button" className="secondary-button" onClick={addQuestion}><Plus size={16} /> Add question</button>
          </div>

          <div className="review-actions">
            <span className="helper-copy">Total across questions: {totalMarks} marks</span>
            <button type="button" className="secondary-button" onClick={() => onSaveDraft(draft)}>
              <Save size={16} /> Save review
            </button>
            <button type="button" className="primary-button" onClick={() => onLockDraft(draft)}>
              <ShieldCheck size={16} /> Lock verified reference
            </button>
          </div>
        </section>
      )}
    </>
  );
}
