import { useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { PageIntro } from './PageIntro';
import { buildComparisonRows, mean, percentage } from './analytics';
import type { Assessment, ComparisonRow } from './types';

const agreementColors = ['#B8A6D9', '#DDEBE5', '#F2AEBE'];

type ComparisonPageProps = {
  assessments: Assessment[];
  comparisons: ComparisonRow[];
};

export function ComparisonPage({ assessments, comparisons }: ComparisonPageProps) {
  const [subjectFilter, setSubjectFilter] = useState('');
  const [assessmentFilter, setAssessmentFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const allRows = useMemo(() => buildComparisonRows(comparisons), [comparisons]);
  const rows = useMemo(
    () => allRows.filter((row) => {
      const date = row.createdAt.slice(0, 10);
      return (
        (!subjectFilter || row.subject === subjectFilter) &&
        (!assessmentFilter || row.assessmentId === Number(assessmentFilter)) &&
        (!dateFrom || date >= dateFrom) &&
        (!dateTo || date <= dateTo)
      );
    }),
    [allRows, assessmentFilter, dateFrom, dateTo, subjectFilter],
  );
  const exactCount = rows.filter((row) => row.status === 'Exact agreement').length;
  const partialCount = rows.filter((row) => row.status === 'Partial agreement').length;
  const disagreementCount = rows.filter((row) => row.status === 'Disagreement').length;
  const mae = mean(rows.map((row) => row.differencePercentagePoints));
  const rmse = rows.length
    ? Math.sqrt(rows.reduce((total, row) => total + row.differencePercentagePoints ** 2, 0) / rows.length)
    : null;
  const withinTolerance = percentage(exactCount + partialCount, rows.length);
  const exactAgreement = percentage(exactCount, rows.length);
  const agreementData = [
    { name: 'Exact agreement', value: exactCount },
    { name: 'Partial agreement', value: partialCount },
    { name: 'Disagreement', value: disagreementCount },
  ];
  const trendData = [...rows.reduce((groups, row) => {
    const date = row.createdAt.slice(0, 10);
    const current = groups.get(date) ?? { date, aiScores: [], teacherScores: [] };
    current.aiScores.push(row.aiPercentage);
    current.teacherScores.push(row.teacherPercentage);
    groups.set(date, current);
    return groups;
  }, new Map<string, { date: string; aiScores: number[]; teacherScores: number[] }>()).values()]
    .sort((left, right) => left.date.localeCompare(right.date))
    .map((group) => ({
      date: group.date,
      'AI average': mean(group.aiScores) ?? 0,
      'Teacher average': mean(group.teacherScores) ?? 0,
    }));
  const subjectData = [...rows.reduce((groups, row) => {
    const current = groups.get(row.subject) ?? { subject: row.subject, aiScores: [], teacherScores: [] };
    current.aiScores.push(row.aiPercentage);
    current.teacherScores.push(row.teacherPercentage);
    groups.set(row.subject, current);
    return groups;
  }, new Map<string, { subject: string; aiScores: number[]; teacherScores: number[] }>()).values()]
    .map((group) => ({
      subject: group.subject,
      'AI average': mean(group.aiScores) ?? 0,
      'Teacher average': mean(group.teacherScores) ?? 0,
    }));
  const barData = rows.map((row) => ({
    label: `${row.studentId} · ${row.questionId}`,
    assessment: `${row.assessmentTitle} v${row.versionNumber}`,
    aiPercentage: row.aiPercentage,
    teacherPercentage: row.teacherPercentage,
  }));
  const comparableAssessments = assessments.filter((assessment) =>
    allRows.some((row) => row.assessmentId === assessment.id),
  );
  const subjects = [...new Set(allRows.map((row) => row.subject).filter(Boolean))].sort();

  return (
    <>
      <PageIntro
        eyebrow="Human reference comparison"
        title="Teacher vs AI Grading Comparison"
        description="See how AI-assigned scores align with teacher-entered reference scores. Agreement is not the same as independently verified accuracy."
      />

      <div className="notice-callout">
        <strong>Metric scope:</strong> only submissions with a valid teacher score on the same assessment scale are included. Verified AI accuracy and teacher accuracy cannot be calculated because the application has no independent reference-standard scores.
      </div>

      <section className="panel filter-panel">
        <div className="filter-heading"><div><p className="eyebrow">Comparison dataset</p><h2>Filter paired scores</h2></div><span className="count-chip">{rows.length} of {allRows.length} pairs</span></div>
        <div className="filter-grid">
          <label className="field"><span>From date</span><input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></label>
          <label className="field"><span>To date</span><input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} /></label>
          <label className="field"><span>Subject</span><select value={subjectFilter} onChange={(event) => setSubjectFilter(event.target.value)}><option value="">All subjects</option>{subjects.map((subject) => <option key={subject} value={subject}>{subject}</option>)}</select></label>
          <label className="field"><span>Assessment</span><select value={assessmentFilter} onChange={(event) => setAssessmentFilter(event.target.value)}><option value="">All assessments</option>{comparableAssessments.map((assessment) => <option key={assessment.id} value={assessment.id}>{assessment.title.trim() || `Assessment ${assessment.id}`}</option>)}</select></label>
        </div>
        <p className="helper-copy">Class/group filtering is unavailable because no class or group field exists in the current data model.</p>
      </section>

      <section className="comparison-metrics">
        <article className="metric-card soft-lilac">
          <span className="metric-label">AI-teacher agreement</span>
          <strong className="metric-value">{withinTolerance === null ? '-' : `${withinTolerance.toFixed(1)}%`}</strong>
          <span className="metric-caption">Exact or within configured disagreement tolerance | {rows.length} comparison pair{rows.length === 1 ? '' : 's'}</span>
        </article>
        <article className="metric-card soft-sage">
          <span className="metric-label">Exact score agreement</span>
          <strong className="metric-value">{exactAgreement === null ? '-' : `${exactAgreement.toFixed(1)}%`}</strong>
          <span className="metric-caption">{exactCount} exact match{exactCount === 1 ? '' : 'es'} / {rows.length} comparison pair{rows.length === 1 ? '' : 's'}</span>
        </article>
        <article className="metric-card soft-rose">
          <span className="metric-label">Mean absolute error</span>
          <strong className="metric-value">{mae === null ? '-' : `${mae.toFixed(2)} pp`}</strong>
          <span className="metric-caption">Mean normalized score difference | {rows.length} comparison pair{rows.length === 1 ? '' : 's'}</span>
        </article>
        <article className="metric-card soft-cream">
          <span className="metric-label">RMSE</span>
          <strong className="metric-value">{rmse === null ? '-' : `${rmse.toFixed(2)} pp`}</strong>
          <span className="metric-caption">Root mean squared percentage-point error | {rows.length} comparison pair{rows.length === 1 ? '' : 's'}</span>
        </article>
        <article className="metric-card metric-unavailable">
          <span className="metric-label">Verified AI accuracy</span>
          <strong className="metric-value">Unavailable</strong>
          <span className="metric-caption">No independent reference-standard scores are stored.</span>
        </article>
      </section>

      {rows.length === 0 ? (
        <div className="empty-state comparison-empty">
          {allRows.length
            ? 'No teacher-AI score pairs match these filters. Adjust the filters to see available comparisons.'
            : 'No comparable teacher marks yet. Add independent teacher marks to imported question answers to populate this analysis.'}
        </div>
      ) : (
        <>
          <div className="comparison-charts">
            <section className="panel">
              <div className="section-header"><div><p className="eyebrow">Paired results</p><h2>AI and teacher scores by question</h2><p className="panel-subtitle">Normalized to each locked question's maximum score.</p></div></div>
              <div className="chart-container tall-chart" style={{ height: Math.max(300, rows.length * 38) }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={barData} layout="vertical" margin={{ top: 8, right: 18, bottom: 8, left: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#E7DFEF" />
                    <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fill: '#776B83', fontSize: 11 }} />
                    <YAxis type="category" dataKey="label" width={130} tick={{ fill: '#776B83', fontSize: 11 }} />
                    <Tooltip formatter={(value: number) => [`${Number(value).toFixed(1)}%`, 'Score']} labelFormatter={(label, payload) => `${payload?.[0]?.payload?.assessment ?? 'Assessment'} - ${label}`} />
                    <Legend />
                    <Bar dataKey="teacherPercentage" name="Teacher score" fill="#9AB9AA" radius={[5, 5, 0, 0]} />
                    <Bar dataKey="aiPercentage" name="AI score" fill="#B8A6D9" radius={[5, 5, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>

            <section className="panel">
              <div className="section-header"><div><p className="eyebrow">Agreement distribution</p><h2>How paired grades align</h2><p className="panel-subtitle">Tolerance follows the current grading rule for each assessment.</p></div></div>
              <div className="chart-layout">
                <div className="chart-container donut-chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={agreementData} dataKey="value" nameKey="name" innerRadius="60%" outerRadius="88%" paddingAngle={3}>
                        {agreementData.map((item, index) => <Cell key={item.name} fill={agreementColors[index]} />)}
                      </Pie>
                      <Tooltip formatter={(value: number) => [`${value} pairs`, 'Count']} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="legend-list">
                  {agreementData.map((item, index) => <div key={item.name} className="legend-item"><span className="legend-dot" style={{ backgroundColor: agreementColors[index] }} /><span>{item.name}</span><strong>{item.value}</strong></div>)}
                  <p className="chart-denominator">Denominator: {rows.length} paired score{rows.length === 1 ? '' : 's'}</p>
                </div>
              </div>
            </section>

            <section className="panel">
              <div className="section-header"><div><p className="eyebrow">Over time</p><h2>AI and teacher score trends</h2><p className="panel-subtitle">Average normalized question score by submission date.</p></div></div>
              {trendData.length > 1 ? (
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={trendData} margin={{ top: 8, right: 18, bottom: 8, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E7DFEF" />
                      <XAxis dataKey="date" tick={{ fill: '#776B83', fontSize: 11 }} />
                      <YAxis domain={[0, 100]} unit="%" tick={{ fill: '#776B83', fontSize: 11 }} />
                      <Tooltip formatter={(value: number) => [`${Number(value).toFixed(1)}%`, 'Average']} />
                      <Legend />
                      <Line type="monotone" dataKey="AI average" stroke="#8E78B9" strokeWidth={3} dot={{ r: 4 }} />
                      <Line type="monotone" dataKey="Teacher average" stroke="#82A693" strokeWidth={3} dot={{ r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="empty-state small">A trend needs paired scores on at least two different dates.</div>
              )}
            </section>

            <section className="panel">
              <div className="section-header"><div><p className="eyebrow">Subject breakdown</p><h2>Average score by subject</h2><p className="panel-subtitle">Teacher reference and AI averages use the same normalized scale.</p></div></div>
              {subjectData.length ? (
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={subjectData} layout="vertical" margin={{ top: 8, right: 20, bottom: 8, left: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#E7DFEF" />
                      <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fill: '#776B83', fontSize: 11 }} />
                      <YAxis type="category" dataKey="subject" width={100} tick={{ fill: '#776B83', fontSize: 11 }} />
                      <Tooltip formatter={(value: number) => [`${Number(value).toFixed(1)}%`, 'Average']} />
                      <Legend />
                      <Bar dataKey="Teacher average" fill="#9AB9AA" radius={[0, 5, 5, 0]} />
                      <Bar dataKey="AI average" fill="#B8A6D9" radius={[0, 5, 5, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : <div className="empty-state small">Subject comparison will appear when paired scores are available.</div>}
            </section>
          </div>

          <section className="panel">
            <div className="section-header">
              <div><p className="eyebrow">Audit detail</p><h2>Detailed score comparison</h2><p className="panel-subtitle">Difference is AI minus teacher score; agreement status uses the configured tolerance.</p></div>
              <span className="count-chip">{rows.length} pair{rows.length === 1 ? '' : 's'}</span>
            </div>
            <div className="table-wrap wide">
              <table>
                <thead><tr><th>Student / attempt</th><th>Assessment / version</th><th>Question</th><th>Subject</th><th>Teacher score</th><th>AI score</th><th>Difference</th><th>Agreement status</th></tr></thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id}>
                      <td className="student-name">{row.studentId}<small>Attempt {row.attemptNumber}</small></td>
                      <td>{row.assessmentTitle} · v{row.versionNumber}</td>
                      <td><strong>{row.questionId}</strong><small>{row.question}</small></td>
                      <td>{row.subject}</td>
                      <td>{row.teacherScore.toFixed(2)}/{row.maximumScore}</td>
                      <td>{row.aiScore.toFixed(2)}/{row.maximumScore}</td>
                      <td>{(row.aiScore - row.teacherScore).toFixed(2)} ({row.differencePercentagePoints.toFixed(2)} pp)</td>
                      <td><span className={`status-pill ${row.status === 'Disagreement' ? 'warning' : 'success'}`}>{row.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="chart-denominator">Comparison denominator: {rows.length} valid teacher-AI score pairs after filters. Teacher scores outside the assessment maximum are excluded.</p>
          </section>
        </>
      )}
    </>
  );
}
