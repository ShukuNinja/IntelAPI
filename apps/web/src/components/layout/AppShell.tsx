import { NavLink, Outlet } from 'react-router-dom'
import {
  Activity, Boxes, ChevronDown, CircleHelp, Clock3, Code2, Command, FileSearch2,
  FlaskConical, FolderKanban, LayoutDashboard, Search, Settings2, ShieldCheck,
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
    {item.label === 'Findings & Evidence' && <span className="nav-count">8</span>}
  </NavLink>
}

export function AppShell() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink to="/" className="brand">
          <span className="brand__mark"><Waves size={21} /></span>
          <span className="brand__copy"><strong>trace<span>line</span></strong><small>API INTELLIGENCE</small></span>
        </NavLink>
        <button className="project-switcher" type="button">
          <span className="project-switcher__icon"><Command size={16} /></span>
          <span className="project-switcher__copy"><strong>Acme Platform</strong><small>Personal workspace</small></span>
          <ChevronDown size={15} />
        </button>
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
          <button className="nav-link nav-link--button" type="button"><CircleHelp size={17} /><span>Help & documentation</span></button>
          <div className="profile">
            <div className="avatar">JD</div><div className="profile__copy"><strong>Jordan Davis</strong><small>Local demo account</small></div><button type="button" aria-label="Profile options"><ChevronDown size={15} /></button>
          </div>
        </div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div className="breadcrumbs"><span>Workspace</span><span className="breadcrumbs__slash">/</span><strong>Acme Platform</strong></div>
          <div className="topbar__actions">
            <span className="demo-indicator"><span /> Demo data</span>
            <button className="icon-button search-shortcut" aria-label="Search" type="button"><Search size={17} /><kbd>⌘ K</kbd></button>
            <button className="icon-button" aria-label="Notifications" type="button"><Activity size={17} /></button>
            <div className="topbar__divider" />
            <div className="avatar avatar--small">JD</div>
          </div>
        </header>
        <main className="main-content"><Outlet /></main>
        <footer className="app-footer"><span><span className="footer-dot" /> System operational <span className="footer-separator">·</span> UI foundation</span><span>Traceline <span className="footer-separator">/</span> Preview build 0.1.0</span></footer>
      </div>
    </div>
  )
}