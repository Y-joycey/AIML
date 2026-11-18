import { useMemo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { mean } from './analytics';
import { PageIntro } from './PageIntro';
import type { Assessment, DashboardData, ResultRow } from './types';

type AnalyticsPageProps = {
  dashboard: DashboardData | null;
  assessments: Assessment[];
  resultsByAssessment: Record<number, ResultRow[]>;
};

export function AnalyticsPage({ dashboard, assessments, resultsByAssessment }: AnalyticsPageProps) {
  const activeAssessments = assessments.filter((assessment) => assessment.is_locked);
  const allResults = useMemo(
    () => activeAssessments.flatMap((assessment) =>
      (resultsByAssessment[assessment.id] ?? []).map((result) => ({ assessment, result })),
    ),
    [activeAssessments, resultsByAssessment],
  );
  const distribution = Object.entries(dashboard?.score_distribution ?? {}).map(([range, count]) => ({ range, count }));
  const trend = [...allResults.reduce((groups, item) => {
    const date = item.result.created_at.slice(0, 10);
    const scores = groups.get(date) ?? [];
    scores.push(item.result.percentage);
    groups.set(date, scores);
    return groups;
  }, new Map<string, number[]>()).entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([date, scores]) => ({ date, 'Average score': mean(scores) ?? 0 }));
  const bySubject = [...allResults.reduce((groups, item) => {
    const scores = groups.get(item.assessment.subject) ?? [];
    scores.push(item.result.percentage);
    groups.set(item.assessment.subject, scores);
    return groups;
  }, new Map<string, number[]>()).entries()]
    .map(([subject, scores]) => ({ subject, 'Average score': mean(scores) ?? 0, submissions: scores.length }));

  return (
    <>
      <PageIntro
        eyebrow="Performance insights"
        title="Understand score patterns across assessments."
        description="All values below are calculated from submitted results and the existing dashboard API; missing data is shown as an empty state."
      />
      <div className="analytics-summary">
        <article className="panel compact-stat"><span className="metric-label">Submissions in view</span><strong>{allResults.length}</strong><small>Across {activeAssessments.length} locked assessments</small></article>
        <article className="panel compact-stat"><span className="metric-label">Average normalized score</span><strong>{allResults.length ? `${(mean(allResults.map(({ result }) => result.percentage)) ?? 0).toFixed(1)}%` : '-'}</strong><small>Per-submission percentage</small></article>
        <article className="panel compact-stat"><span className="metric-label">Assessment subjects</span><strong>{new Set(activeAssessments.map((assessment) => assessment.subject)).size || '-'}</strong><small>From locked references</small></article>
      </div>
      <div className="dashboard-grid">
        <section className="panel">
          <div className="section-header"><div><p className="eyebrow">Distribution</p><h2>Submission score bands</h2><p className="panel-subtitle">Counts by earned percentage interval.</p></div></div>
          {distribution.some((item) => item.count > 0) ? (
            <div className="chart-container">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={distribution} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E7DFEF" />
                  <XAxis dataKey="range" tick={{ fill: '#776B83', fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fill: '#776B83', fontSize: 11 }} />
                  <Tooltip formatter={(value: number) => [`${value} submissions`, 'Count']} />
                  <Bar dataKey="count" name="Submissions" fill="#B8A6D9" radius={[7, 7, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : <div className="empty-state small">Score bands will appear after submissions are graded.</div>}
        </section>

        <section className="panel">
          <div className="section-header"><div><p className="eyebrow">Progress</p><h2>Score trend over time</h2><p className="panel-subtitle">Average earned percentage by submission date.</p></div></div>
          {trend.length > 1 ? (
            <div className="chart-container">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trend} margin={{ top: 8, right: 18, bottom: 8, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E7DFEF" />
                  <XAxis dataKey="date" tick={{ fill: '#776B83', fontSize: 11 }} />
                  <YAxis domain={[0, 100]} unit="%" tick={{ fill: '#776B83', fontSize: 11 }} />
                  <Tooltip formatter={(value: number) => [`${Number(value).toFixed(1)}%`, 'Average']} />
                  <Line type="monotone" dataKey="Average score" stroke="#8E78B9" strokeWidth={3} dot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : <div className="empty-state small">A performance trend needs submissions on at least two dates.</div>}
        </section>

        <section className="panel">
          <div className="section-header"><div><p className="eyebrow">Subject breakdown</p><h2>Average score by subject</h2><p className="panel-subtitle">Based on all graded submissions in each subject.</p></div></div>
          {bySubject.length ? (
            <div className="chart-container">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={bySubject} layout="vertical" margin={{ top: 8, right: 20, bottom: 8, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#E7DFEF" />
                  <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fill: '#776B83', fontSize: 11 }} />
                  <YAxis type="category" dataKey="subject" width={120} tick={{ fill: '#776B83', fontSize: 11 }} />
                  <Tooltip formatter={(value: number, name: string, item) => [`${Number(value).toFixed(1)}% | ${item.payload.submissions} submissions`, name]} />
                  <Bar dataKey="Average score" fill="#9AB9AA" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : <div className="empty-state small">Subject analysis will appear when assessment submissions are available.</div>}
        </section>

        <section className="panel">
          <div className="section-header compact"><div><p className="eyebrow">Metric notes</p><h2>Interpret with context</h2></div></div>
          <ul className="notice-list">
            <li>Average scores are normalized to each submission's maximum marks.</li>
            <li>Score trends describe submitted results; they do not establish learning gain or causal impact.</li>
            <li>Teacher-AI agreement is available on the separate comparison page and is not accuracy.</li>
          </ul>
        </section>
      </div>
    </>
  );
}
