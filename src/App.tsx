import { lazy, Suspense, useEffect, useState } from 'react';
import type { ChangeEvent } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './AppShell';
import { normalizeComparisonRows } from './analytics';
import type {
  Assessment,
  AssessmentDraft,
  ComparisonRow,
  ComparisonRecord,
  CSVPreview,
  DashboardData,
  QuestionAnswerRow,
  ResultRow,
} from './types';

const API_BASE = 'http://localhost:8000/api';
const DashboardPage = lazy(() => import('./DashboardPage').then((module) => ({ default: module.DashboardPage })));
const AssessmentsPage = lazy(() => import('./AssessmentsPage').then((module) => ({ default: module.AssessmentsPage })));
const GradingPage = lazy(() => import('./GradingPage').then((module) => ({ default: module.GradingPage })));
const ComparisonPage = lazy(() => import('./ComparisonPage').then((module) => ({ default: module.ComparisonPage })));
const AnalyticsPage = lazy(() => import('./AnalyticsPage').then((module) => ({ default: module.AnalyticsPage })));
const ReportsPage = lazy(() => import('./ReportsPage').then((module) => ({ default: module.ReportsPage })));

type AssessmentUploadMetadata = {
  title: string;
  subject: string;
  language: string;
  assessment_id?: number;
};

function responseMessage(payload: unknown, fallback: string): string {
  if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (typeof detail === 'object' && detail !== null && 'message' in detail) {
      return String((detail as { message?: unknown }).message ?? fallback);
    }
  }
  return fallback;
}

function App() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [selectedAssessmentId, setSelectedAssessmentId] = useState<number | null>(null);
  const [resultsByAssessment, setResultsByAssessment] = useState<Record<number, ResultRow[]>>({});
  const [questionAnswersByAssessment, setQuestionAnswersByAssessment] = useState<Record<number, QuestionAnswerRow[]>>({});
  const [comparisons, setComparisons] = useState<ComparisonRow[]>([]);
  const [assessmentDraft, setAssessmentDraft] = useState<AssessmentDraft | null>(null);
  const [draftAssessmentId, setDraftAssessmentId] = useState<number | null>(null);
  const [csvPreview, setCsvPreview] = useState<CSVPreview | null>(null);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvAssessmentId, setCsvAssessmentId] = useState<number | null>(null);
  const [statusMessage, setStatusMessage] = useState('');

  const activeAssessmentId = selectedAssessmentId ?? assessments.find((assessment) => assessment.is_locked)?.id ?? null;
  const activeAssessment = assessments.find((assessment) => assessment.id === activeAssessmentId) ?? null;
  const activeResults = activeAssessmentId ? resultsByAssessment[activeAssessmentId] ?? [] : [];
  const activeQuestionAnswers = activeAssessmentId ? questionAnswersByAssessment[activeAssessmentId] ?? [] : [];

  useEffect(() => {
    void refreshData();
  }, []);

  const refreshData = async () => {
    try {
      const [dashboardResponse, assessmentsResponse, comparisonsResponse] = await Promise.all([
        fetch(`${API_BASE}/dashboard`),
        fetch(`${API_BASE}/assessments`),
        fetch(`${API_BASE}/comparisons`),
      ]);
      if (!dashboardResponse.ok || !assessmentsResponse.ok || !comparisonsResponse.ok) {
        throw new Error('The backend did not return dashboard, assessment, and comparison data successfully.');
      }

      const [dashboardData, assessmentData, comparisonData] = await Promise.all([
        dashboardResponse.json() as Promise<DashboardData>,
        assessmentsResponse.json() as Promise<Assessment[]>,
        comparisonsResponse.json() as Promise<ComparisonRecord[]>,
      ]);
      const resultEntries = await Promise.all(
        assessmentData.map(async (assessment) => {
          const [resultResponse, answerResponse] = await Promise.all([
            fetch(`${API_BASE}/results/${assessment.id}`),
            fetch(`${API_BASE}/assessments/${assessment.id}/question-answers`),
          ]);
          if (!resultResponse.ok || !answerResponse.ok) {
            throw new Error(`Unable to load grading records for assessment ${assessment.id}.`);
          }
          const allResults = (await resultResponse.json()) as ResultRow[];
          const answers = (await answerResponse.json()) as QuestionAnswerRow[];
          return {
            assessmentId: assessment.id,
            results: allResults.filter((result) => result.version_id !== null),
            answers,
          };
        }),
      );

      setDashboard(dashboardData);
      setAssessments(assessmentData);
      setComparisons(normalizeComparisonRows(comparisonData));
      setResultsByAssessment(Object.fromEntries(resultEntries.map((entry) => [entry.assessmentId, entry.results])));
      setQuestionAnswersByAssessment(Object.fromEntries(resultEntries.map((entry) => [entry.assessmentId, entry.answers])));
      setSelectedAssessmentId((current) =>
        current && assessmentData.some((assessment) => assessment.id === current)
          ? current
          : assessmentData.find((assessment) => assessment.is_locked)?.id ?? assessmentData[0]?.id ?? null,
      );
    } catch (error) {
      console.error('Unable to refresh GradeSense AI data', error);
      setStatusMessage('Unable to load application data. Confirm the FastAPI backend is running and try again.');
    }
  };

  const handleUploadDocument = async (file: File, metadata: AssessmentUploadMetadata) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', metadata.title);
    formData.append('subject', metadata.subject);
    formData.append('language', metadata.language);
    if (metadata.assessment_id) formData.append('assessment_id', String(metadata.assessment_id));
    try {
      const response = await fetch(`${API_BASE}/assessments/upload`, { method: 'POST', body: formData });
      const payload = (await response.json()) as { assessment_id?: number; version?: AssessmentDraft; detail?: unknown };
      if (!response.ok || !payload.assessment_id || !payload.version) {
        setStatusMessage(responseMessage(payload, 'Assessment document could not be processed.'));
        return;
      }
      setDraftAssessmentId(payload.assessment_id);
      setAssessmentDraft(payload.version);
      setSelectedAssessmentId(payload.assessment_id);
      setStatusMessage('Document extracted locally. Review every question, answer, and rubric before locking.');
      await refreshData();
    } catch (error) {
      console.error('Unable to upload assessment document', error);
      setStatusMessage('Assessment upload failed because the backend or local model could not be reached.');
    }
  };

  const handleLoadDraft = async (assessmentId: number, versionId: number) => {
    try {
      const response = await fetch(`${API_BASE}/assessments/${assessmentId}/versions/${versionId}`);
      const payload = (await response.json()) as AssessmentDraft & { detail?: unknown };
      if (!response.ok) {
        setStatusMessage(responseMessage(payload, 'Assessment draft could not be loaded.'));
        return;
      }
      setDraftAssessmentId(assessmentId);
      setAssessmentDraft(payload);
      setSelectedAssessmentId(assessmentId);
    } catch (error) {
      console.error('Unable to load assessment draft', error);
      setStatusMessage('Assessment draft could not be loaded from the backend.');
    }
  };

  const handleSaveDraft = async (draft: AssessmentDraft) => {
    if (!draftAssessmentId) return;
    try {
      const response = await fetch(`${API_BASE}/assessments/${draftAssessmentId}/versions/${draft.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: draft.title,
          subject: draft.subject,
          language: draft.language,
          questions: draft.questions,
        }),
      });
      const payload = (await response.json()) as AssessmentDraft & { detail?: unknown };
      if (!response.ok) {
        setStatusMessage(responseMessage(payload, 'Assessment review could not be saved.'));
        return;
      }
      setAssessmentDraft(payload);
      setStatusMessage('Review changes saved. Lock the reference when every field is verified.');
      await refreshData();
    } catch (error) {
      console.error('Unable to save assessment review', error);
      setStatusMessage('Assessment review could not be saved because the backend could not be reached.');
    }
  };

  const handleLockDraft = async (draft: AssessmentDraft) => {
    if (!draftAssessmentId) return;
    try {
      const saveResponse = await fetch(`${API_BASE}/assessments/${draftAssessmentId}/versions/${draft.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: draft.title,
          subject: draft.subject,
          language: draft.language,
          questions: draft.questions,
        }),
      });
      const savedDraft = (await saveResponse.json()) as AssessmentDraft & { detail?: unknown };
      if (!saveResponse.ok) {
        setStatusMessage(responseMessage(savedDraft, 'Assessment review could not be saved.'));
        return;
      }
      const response = await fetch(
        `${API_BASE}/assessments/${draftAssessmentId}/versions/${draft.id}/lock`,
        { method: 'POST' },
      );
      const payload = (await response.json()) as Assessment & { detail?: unknown };
      if (!response.ok) {
        setStatusMessage(responseMessage(payload, 'Assessment reference could not be locked.'));
        return;
      }
      setAssessmentDraft(null);
      setDraftAssessmentId(null);
      setStatusMessage('Assessment reference locked. New grading records will use this immutable version.');
      await refreshData();
    } catch (error) {
      console.error('Unable to lock assessment reference', error);
      setStatusMessage('Assessment reference could not be locked because the backend could not be reached.');
    }
  };

  const handleCsvUpload = async (file: File, versionId: number) => {
    if (!activeAssessmentId || !activeAssessment?.version_history.some(
      (version) => version.id === versionId && version.status === 'locked',
    )) {
      setStatusMessage('Select an assessment with a locked reference before uploading answers.');
      return;
    }
    setCsvFile(file);
    setCsvPreview(null);
    setCsvAssessmentId(activeAssessmentId);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('assessment_id', String(activeAssessmentId));
    formData.append('version_id', String(versionId));
    try {
      const response = await fetch(`${API_BASE}/submissions/csv-preview`, { method: 'POST', body: formData });
      const payload = (await response.json()) as CSVPreview & { detail?: unknown };
      if (!response.ok) {
        setStatusMessage(responseMessage(payload, 'CSV preview failed.'));
        return;
      }
      setCsvPreview(payload);
      setStatusMessage(
        `CSV preview: ${payload.rows.length} answer rows, ${payload.errors.length} validation errors.`,
      );
    } catch (error) {
      console.error('Unable to preview CSV', error);
      setStatusMessage('CSV preview failed because the backend could not be reached.');
    }
  };

  const handleImportCsv = async (startNewAttempt: boolean, versionId: number) => {
    if (!csvFile || !csvPreview || !activeAssessmentId || csvAssessmentId !== activeAssessmentId || csvPreview.version_id !== versionId) return;
    if (csvPreview.errors.length > 0) {
      setStatusMessage('Fix every CSV validation error before importing.');
      return;
    }
    const formData = new FormData();
    formData.append('file', csvFile);
    formData.append('assessment_id', String(activeAssessmentId));
    formData.append('version_id', String(versionId));
    formData.append('start_new_attempt', String(startNewAttempt));
    try {
      const response = await fetch(`${API_BASE}/submissions/import`, { method: 'POST', body: formData });
      const payload = (await response.json()) as { created?: number; batch_id?: number; detail?: unknown };
      if (!response.ok) {
        setStatusMessage(responseMessage(payload, 'CSV import failed.'));
        return;
      }
      setStatusMessage(`Imported ${payload.created ?? 0} student attempts. Batch ${payload.batch_id} is ready for teacher review.`);
      setCsvFile(null);
      setCsvPreview(null);
      setCsvAssessmentId(null);
      await refreshData();
    } catch (error) {
      console.error('Unable to import CSV', error);
      setStatusMessage('CSV import failed because the backend could not be reached.');
    }
  };

  const handleSaveTeacherMark = async (questionAnswerId: number, score: number, notes: string) => {
    try {
      const response = await fetch(`${API_BASE}/question-answers/${questionAnswerId}/teacher-mark`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ score, notes }),
      });
      const payload = (await response.json()) as { detail?: unknown };
      if (!response.ok) {
        setStatusMessage(responseMessage(payload, 'Teacher mark could not be saved.'));
        return;
      }
      setStatusMessage('Teacher mark saved independently; the AI score was not changed.');
      await refreshData();
    } catch (error) {
      console.error('Unable to save teacher mark', error);
      setStatusMessage('Teacher mark could not be saved because the backend could not be reached.');
    }
  };

  const handleExportBatch = async (batchId: number) => {
    try {
      const response = await fetch(`${API_BASE}/submissions/export/${batchId}`);
      if (!response.ok) {
        const payload = await response.json() as { detail?: unknown };
        setStatusMessage(responseMessage(payload, 'Marked CSV export failed.'));
        return;
      }
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `teacher-marks-${batchId}.csv`;
      anchor.click();
      URL.revokeObjectURL(url);
      setStatusMessage('Teacher-mark CSV downloaded with the original columns preserved.');
    } catch (error) {
      console.error('Unable to export teacher marks', error);
      setStatusMessage('Marked CSV export failed because the backend could not be reached.');
    }
  };

  const clearCsvPreview = () => {
    setCsvPreview(null);
    setCsvFile(null);
    setCsvAssessmentId(null);
  };

  const selectAssessment = (id: number) => {
    setSelectedAssessmentId(id);
    clearCsvPreview();
  };

  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Suspense fallback={<div className="page-loading" role="status">Loading page...</div>}>
        <Routes>
          <Route element={<AppShell statusMessage={statusMessage} />}>
            <Route
              path="/"
              element={
                <DashboardPage
                  dashboard={dashboard}
                  assessments={assessments}
                  resultsByAssessment={resultsByAssessment}
                  comparisons={comparisons}
                />
              }
            />
            <Route
              path="/assessments"
              element={
                <AssessmentsPage
                  assessments={assessments}
                  selectedAssessmentId={activeAssessmentId}
                  assessmentDraft={assessmentDraft}
                  onUploadDocument={handleUploadDocument}
                  onLoadDraft={handleLoadDraft}
                  onSaveDraft={handleSaveDraft}
                  onLockDraft={handleLockDraft}
                  onSelectAssessment={selectAssessment}
                />
              }
            />
            <Route
              path="/ai-grading"
              element={
                <GradingPage
                  mode="ai"
                  assessments={assessments}
                  selectedAssessmentId={activeAssessmentId}
                  onSelectAssessment={selectAssessment}
                  onCsvUpload={handleCsvUpload}
                  onImportCsv={handleImportCsv}
                  csvPreview={csvPreview}
                  onClearCsvPreview={clearCsvPreview}
                  results={activeResults}
                  questionAnswers={activeQuestionAnswers}
                  onSaveTeacherMark={handleSaveTeacherMark}
                  onExportBatch={handleExportBatch}
                />
              }
            />
            <Route
              path="/teacher-grading"
              element={
                <GradingPage
                  mode="teacher"
                  assessments={assessments}
                  selectedAssessmentId={activeAssessmentId}
                  onSelectAssessment={selectAssessment}
                  onCsvUpload={handleCsvUpload}
                  onImportCsv={handleImportCsv}
                  csvPreview={csvPreview}
                  onClearCsvPreview={clearCsvPreview}
                  results={activeResults}
                  questionAnswers={activeQuestionAnswers}
                  onSaveTeacherMark={handleSaveTeacherMark}
                  onExportBatch={handleExportBatch}
                />
              }
            />
            <Route path="/comparison" element={<ComparisonPage assessments={assessments} comparisons={comparisons} />} />
            <Route
              path="/analytics"
              element={<AnalyticsPage dashboard={dashboard} assessments={assessments} resultsByAssessment={resultsByAssessment} />}
            />
            <Route
              path="/reports"
              element={<ReportsPage dashboard={dashboard} assessments={assessments} resultsByAssessment={resultsByAssessment} />}
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

export default App;
