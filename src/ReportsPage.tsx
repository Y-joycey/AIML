import { PageIntro } from './PageIntro';
import { ResultsTable } from './ResultsTable';
import type { Assessment, DashboardData, ResultRow } from './types';

type ReportsPageProps = {
  dashboard: DashboardData | null;
  assessments: Assessment[];
  resultsByAssessment: Record<number, ResultRow[]>;
};

export function ReportsPage({ dashboard, assessments, resultsByAssessment }: ReportsPageProps) {
  return (
    <>
      <PageIntro
        eyebrow="Assessment records"
        title="Review grading activity and submitted results."
        description="This report view summarizes existing assessment and submission records. It does not create or export new report data."
      />
      <div className="analytics-summary">
        <article className="panel compact-stat"><span className="metric-label">Assessments</span><strong>{dashboard?.total_assessments ?? '-'}</strong><small>Available in the assessment API</small></article>
        <article className="panel compact-stat"><span className="metric-label">Students represented</span><strong>{dashboard?.total_students ?? '-'}</strong><small>Distinct submitted student IDs</small></article>
        <article className="panel compact-stat"><span className="metric-label">Graded submissions</span><strong>{dashboard?.graded_submissions ?? '-'}</strong><small>From the current dashboard summary</small></article>
      </div>
      <section className="panel">
        <div className="section-header">
          <div><p className="eyebrow">Submission register</p><h2>Results across assessments</h2><p className="panel-subtitle">Data comes from each assessment's existing results endpoint.</p></div>
        </div>
        <ResultsTable assessments={assessments} resultsByAssessment={resultsByAssessment} />
      </section>
      <section className="panel">
        <div className="section-header compact"><div><p className="eyebrow">Recent activity</p><h2>Latest grading actions</h2></div></div>
        {dashboard?.recent_activities.length ? (
          <div className="activity-list">
            {dashboard.recent_activities.map((activity, index) => (
              <div key={`${activity.title}-${index}`} className="activity-item">
                <div><strong>{activity.title}</strong><span>{activity.time}</span></div>
                <span className={`status-pill ${activity.status === 'approved' ? 'success' : 'warning'}`}>{activity.status}</span>
              </div>
            ))}
          </div>
        ) : <div className="empty-state small">Recent grading activity will appear here.</div>}
      </section>
    </>
  );
}
