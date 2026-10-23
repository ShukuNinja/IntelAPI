import { NavLink, Outlet } from 'react-router-dom'
import {
  Activity, Boxes, Clock3, Code2, Command, FileSearch2,
  FlaskConical, FolderKanban, LayoutDashboard, Settings2, ShieldCheck,
  Sparkles, Waves, type LucideIcon,
} from 'lucide-react'

type NavItem = { label: string; to: string; icon: LucideIcon }
const primary: NavItem[] = [
  { label: 'Overview', to: '/', icon: LayoutDashboard },
  { label: 'API Workspace', to: '/workspace', icon: Code2 },
  { label: 'Health Checks', to: '/health', icon: Activity },
  { label: 'API Explorer', to: '/explorer', icon: FileSearch2 },
  { label: 'Test Campaigns', to: '/campaigns', icon: FlaskConical },
  { label: 'Findings & Evidence', to: '/findings', icon: ShieldCheck },
]
const workspace: NavItem[] = [
  { label: 'Collections', to: '/collections', icon: FolderKanban },
  { label: 'Environments', to: '/environments', icon: Boxes },
  { label: 'Request History', to: '/history', icon: Clock3 },
]

function SidebarLink({ item }: { item: NavItem }) {
  const Icon = item.icon
  return <NavLink to={item.to} end={item.to === '/'} className={({ isActive }) => `nav-link${isActive ? ' nav-link--active' : ''}`}>
    <Icon size={17} strokeWidth={1.8} /><span>{item.label}</span>
  </NavLink>
}

export function AppShell() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink to="/" className="brand">
          <span className="brand__mark"><Waves size={21} /></span>
          <span className="brand__copy"><strong>Intel<span>API</span></strong><small>API INTELLIGENCE</small></span>
        </NavLink>
        <div className="project-switcher">
          <span className="project-switcher__icon"><Command size={16} /></span>
          <span className="project-switcher__copy"><strong>Local workspace</strong><small>Single-user mode</small></span>
        </div>
        <div className="nav-section-label">PLATFORM</div>
        <nav className="nav-list">{primary.map((item) => <SidebarLink key={item.to} item={item} />)}</nav>
        <div className="nav-section-label nav-section-label--spaced">WORKSPACE</div>
        <nav className="nav-list">{workspace.map((item) => <SidebarLink key={item.to} item={item} />)}</nav>
        <div className="sidebar__bottom">
          <div className="ai-card">
            <span className="ai-card__icon"><Sparkles size={16} /></span>
            <strong>Adaptive testing</strong>
            <p>Explore beyond the happy path.</p>
            <NavLink to="/campaigns">View campaigns <span>↗</span></NavLink>
          </div>
          <SidebarLink item={{ label: 'Settings', to: '/settings', icon: Settings2 }} />
          <div className="profile">
            <div className="avatar">LW</div><div className="profile__copy"><strong>Local user</strong><small>Authentication not configured</small></div>
          </div>
        </div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div className="breadcrumbs"><span>Workspace</span><span className="breadcrumbs__slash">/</span><strong>Acme Platform</strong></div>
          <div className="topbar__actions">
            <span className="demo-indicator"><span /> Single-user mode</span>
            <div className="avatar avatar--small">LW</div>
          </div>
        </header>
        <main className="main-content"><Outlet /></main>
        <footer className="app-footer"><span>Local single-user workspace</span><span>IntelAPI <span className="footer-separator">/</span> 0.1.0</span></footer>
      </div>
    </div>
  )
}
