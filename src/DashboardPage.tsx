import { ArrowUpRight, BookOpenText, Bot, ChartColumnBig, FileSpreadsheet, Users } from 'lucide-react';
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { Link } from 'react-router-dom';
import { mean, percentage } from './analytics';
import type { Assessment, ComparisonRow, DashboardData, ResultRow } from './types';

const chartColors = ['#B8A6D9', '#D8CBEA', '#DDEBE5', '#F2E2E8'];

type DashboardPageProps = {
  dashboard: DashboardData | null;
  assessments: Assessment[];
  resultsByAssessment: Record<number, ResultRow[]>;
  comparisons: ComparisonRow[];
};

export function DashboardPage({ dashboard, assessments, resultsByAssessment, comparisons }: DashboardPageProps) {
  const withinTolerance = comparisons.filter((item) => item.status !== 'Disagreement').length;
  const agreement = percentage(withinTolerance, comparisons.length);
  const averageAiPercentage = mean(
    assessments.flatMap((assessment) =>
      (resultsByAssessment[assessment.id] ?? []).map((result) =>
        result.maximum_score > 0 ? (result.total_score / result.maximum_score) * 100 : 0,
      ),
    ),
  );
  const cards = [
    { label: 'Total students', value: dashboard?.total_students ?? '-', icon: Users, tone: 'soft-lilac' },
    { label: 'Assessments', value: dashboard?.total_assessments ?? '-', icon: BookOpenText, tone: 'soft-sage' },
    { label: 'Graded submissions', value: dashboard?.graded_submissions ?? '-', icon: Bot, tone: 'soft-rose' },
    { label: 'Pending reviews', value: dashboard?.pending_reviews ?? '-', icon: ChartColumnBig, tone: 'soft-cream' },
  ];
  const distribution = Object.entries(dashboard?.score_distribution ?? {}).map(([range, count]) => ({
    range,
    count,
  }));
  const activities = dashboard?.recent_activities ?? [];

  return (
    <>
      <section className="welcome-panel">
        <div>
          <p className="eyebrow">Your assessment workspace</p>
          <h2>Clear insights for more thoughtful assessment.</h2>
          <p>Review assessment activity, explore score patterns, and keep teacher oversight at the center.</p>
        </div>
        <Link className="primary-button" to="/assessments">
          Upload assessment <ArrowUpRight size={16} />
        </Link>
      </section>

      <section className="metric-grid dashboard-metrics" aria-label="Application summary">
        {cards.map(({ label, value, icon: Icon, tone }) => (
          <article key={label} className={`metric-card ${tone}`}>
            <div className="metric-card-top">
              <span className="metric-label">{label}</span>
              <span className="metric-icon"><Icon size={17} /></span>
            </div>
            <div className="metric-value">{value}</div>
            <div className="metric-caption">From current application data</div>
          </article>
        ))}
        <article className="metric-card soft-lilac">
          <div className="metric-card-top">
            <span className="metric-label">AI-teacher agreement</span>
            <span className="metric-icon"><ChartColumnBig size={17} /></span>
          </div>
          <div className="metric-value">{agreement === null ? '-' : `${agreement.toFixed(1)}%`}</div>
          <div className="metric-caption">
            {comparisons.length
              ? `Within tolerance | ${comparisons.length} paired score${comparisons.length === 1 ? '' : 's'}`
              : 'No teacher reference scores yet'}
          </div>
        </article>
        <article className="metric-card soft-sage">
          <div className="metric-card-top">
            <span className="metric-label">Average AI score</span>
            <span className="metric-icon"><Bot size={17} /></span>
          </div>
          <div className="metric-value">{averageAiPercentage === null ? '-' : `${averageAiPercentage.toFixed(1)}%`}</div>
          <div className="metric-caption">Normalized by each assessment maximum</div>
        </article>
      </section>

      <div className="dashboard-grid">
        <section className="panel chart-panel">
          <div className="section-header">
            <div>
              <p className="eyebrow">Learner outcomes</p>
              <h2>Score distribution</h2>
              <p className="panel-subtitle">Submission counts by earned percentage range.</p>
            </div>
            <Link className="text-link" to="/analytics">View analytics <ArrowUpRight size={14} /></Link>
          </div>
          {distribution.some((item) => item.count > 0) ? (
            <div className="chart-layout">
              <div className="chart-container donut-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={distribution} dataKey="count" nameKey="range" innerRadius="62%" outerRadius="88%" paddingAngle={3}>
                      {distribution.map((item, index) => <Cell key={item.range} fill={chartColors[index % chartColors.length]} />)}
                    </Pie>
                    <Tooltip formatter={(value: number) => [`${value} submissions`, 'Count']} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="legend-list">
                {distribution.map((item, index) => (
                  <div key={item.range} className="legend-item">
                    <span className="legend-dot" style={{ backgroundColor: chartColors[index % chartColors.length] }} />
                    <span>{item.range}%</span><strong>{item.count}</strong>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="empty-state">Score distribution will appear after submissions are graded.</div>
          )}
        </section>

        <section className="panel">
          <div className="section-header">
            <div>
              <p className="eyebrow">Latest updates</p>
              <h2>Recent grading activity</h2>
            </div>
            <FileSpreadsheet size={19} className="muted-icon" />
          </div>
          {activities.length ? (
            <div className="activity-list">
              {activities.map((activity, index) => (
                <div key={`${activity.title}-${index}`} className="activity-item">
                  <div><strong>{activity.title}</strong><span>{activity.time}</span></div>
                  <span className={`status-pill ${activity.status === 'approved' ? 'success' : 'warning'}`}>{activity.status}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state small">Grading activity will appear here.</div>
          )}
        </section>

        <section className="panel quick-links-panel">
          <div className="section-header">
            <div><p className="eyebrow">Continue your work</p><h2>Quick navigation</h2></div>
          </div>
          <div className="quick-links">
            <Link to="/assessments"><BookOpenText size={18} /><span><strong>Manage assessments</strong><small>Upload, review, and lock references</small></span><ArrowUpRight size={16} /></Link>
            <Link to="/ai-grading"><Bot size={18} /><span><strong>Grade submissions</strong><small>Import student-answer CSV files</small></span><ArrowUpRight size={16} /></Link>
            <Link to="/comparison"><ChartColumnBig size={18} /><span><strong>Compare grades</strong><small>Explore paired teacher and AI scores</small></span><ArrowUpRight size={16} /></Link>
          </div>
        </section>

        <section className="panel">
          <div className="section-header compact"><h2>Responsible AI</h2></div>
          <ul className="notice-list">
            <li>AI scores are advisory and require teacher review before official use.</li>
            <li>Teacher-AI agreement is not a measure of independently verified accuracy.</li>
            <li>Comparison metrics use only submissions with a valid teacher reference score.</li>
          </ul>
        </section>
      </div>
    </>
  );
}
