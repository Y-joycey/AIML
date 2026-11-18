import {
  Bell,
  BookOpenText,
  Bot,
  ChartColumnBig,
  FileSpreadsheet,
  LayoutGrid,
  Scale,
  ShieldCheck,
  Sparkles,
  UserCircle2,
  UserPen,
} from 'lucide-react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';

const navigation = [
  { label: 'Dashboard', path: '/', icon: LayoutGrid, end: true },
  { label: 'Assessments', path: '/assessments', icon: BookOpenText },
  { label: 'AI Grading', path: '/ai-grading', icon: Bot },
  { label: 'Teacher Grading', path: '/teacher-grading', icon: UserPen },
  { label: 'Grading Comparison', path: '/comparison', icon: Scale },
  { label: 'Performance Analytics', path: '/analytics', icon: ChartColumnBig },
  { label: 'Reports', path: '/reports', icon: FileSpreadsheet },
];

const pageTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/assessments': 'Assessment management',
  '/ai-grading': 'AI grading',
  '/teacher-grading': 'Teacher grading',
  '/comparison': 'Teacher vs AI grading comparison',
  '/analytics': 'Performance analytics',
  '/reports': 'Reports',
};

type AppShellProps = {
  statusMessage: string;
};

export function AppShell({ statusMessage }: AppShellProps) {
  const { pathname } = useLocation();
  const pageTitle = pageTitles[pathname] ?? 'GradeSense AI';

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">
            <Sparkles size={18} />
          </div>
          <div>
            <p className="eyebrow">AI EDU PLATFORM</p>
            <h2>GradeSense AI</h2>
          </div>
        </div>

        <nav className="nav-stack" aria-label="Main navigation">
          {navigation.map(({ label, path, icon: Icon, end }) => (
            <NavLink
              key={path}
              to={path}
              end={end}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="mini-panel">
            <ShieldCheck size={18} />
            <div>
              <strong>Review mode</strong>
              <span>Teacher oversight</span>
            </div>
          </div>
        </div>
      </aside>

      <main className="content-shell">
        <header className="topbar">
          <div>
            <p className="eyebrow text-muted">
              {pathname === '/' ? 'Workspace overview' : <><Link className="breadcrumb-link" to="/">Dashboard</Link> / {pageTitle}</>}
            </p>
            <h1>{pageTitle}</h1>
          </div>
          <div className="topbar-actions">
            <div className="status-pill success">
              <ShieldCheck size={14} />
              AI scores are advisory
            </div>
            <div className="topbar-icon" aria-label="Notifications">
              <Bell size={18} />
            </div>
            <div className="profile-chip">
              <div className="avatar-circle">
                <UserCircle2 size={18} />
              </div>
              <div>
                <strong>Teacher</strong>
                <span>Admin</span>
              </div>
            </div>
          </div>
        </header>

        {statusMessage && (
          <div className="status-banner" role="status">
            {statusMessage}
          </div>
        )}
        <Outlet />
      </main>
    </div>
  );
}
