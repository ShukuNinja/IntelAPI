
import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  Activity,
  Boxes,
  ChevronDown,
  CircleHelp,
  Clock3,
  Code2,
  Command,
  FileSearch2,
  FlaskConical,
  FolderKanban,
  LayoutDashboard,
  LogOut,
  Settings2,
  ShieldCheck,
  Sparkles,
  Waves,
  type LucideIcon,
} from 'lucide-react'
import { useAuth } from '../../features/auth/AuthContext'
import { ProjectProvider, useProject } from '../../features/projects/ProjectContext'

type NavItem = {
  label: string
  to: string
  icon: LucideIcon
}

const primary: NavItem[] = [
  { label: 'Overview', to: '/', icon: LayoutDashboard },
  { label: 'API Workspace', to: '/workspace', icon: Code2 },
  { label: 'Health Checks', to: '/health', icon: Activity },
  { label: 'API Explorer', to: '/explorer', icon: FileSearch2 },
  { label: 'Test Campaigns', to: '/campaigns', icon: FlaskConical },
  { label: 'Findings & Evidence', to: '/findings', icon: ShieldCheck },
  { label: 'Projects', to: '/projects', icon: FolderKanban },
]

const workspace: NavItem[] = [
  { label: 'Collections', to: '/collections', icon: FolderKanban },
  { label: 'Environments', to: '/environments', icon: Boxes },
  { label: 'Request History', to: '/history', icon: Clock3 },
]

function SidebarLink({ item }: { item: NavItem }) {
  const Icon = item.icon

  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      className={({ isActive }) =>
        `nav-link${isActive ? ' nav-link--active' : ''}`
      }
    >
      <Icon size={17} strokeWidth={1.8} />
      <span>{item.label}</span>
      {item.label === 'Findings & Evidence' && (
        <span className="nav-count">8</span>
      )}
    </NavLink>
  )
}

function AppShellContent() {
  const { user, logout } = useAuth()
  const { projects, project, selectProject, loading: projectsLoading } = useProject()
  const navigate = useNavigate()
  const [logoutError, setLogoutError] = useState<string | null>(null)

  const displayName = user?.display_name?.trim() || user?.email || 'User'
  const firstName = displayName.split(/\s+/)[0]
  const initials = firstName.charAt(0).toUpperCase()

  async function handleLogout() {
    setLogoutError(null)

    try {
      await logout()
      navigate('/login', { replace: true })
    } catch (error) {
      setLogoutError(
        error instanceof Error ? error.message : 'Unable to sign out.',
      )
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink to="/" className="brand">
          <span className="brand__mark">
            <Waves size={21} />
          </span>
          <span className="brand__copy">
            <strong>
              IntelAPI
            </strong>
            <small>API INTELLIGENCE</small>
          </span>
        </NavLink>

        <label className="project-switcher" aria-label="Select project">
          <span className="project-switcher__icon">
            <Command size={16} />
          </span>
          <span className="project-switcher__copy">
            <strong>{project?.name ?? (projectsLoading ? 'Loading projects…' : 'No project selected')}</strong>
            <small>{project ? 'Active project' : 'Create a project to begin'}</small>
          </span>
          <ChevronDown size={15} />
          <select aria-label="Active project" value={project?.id ?? ''} onChange={(event) => selectProject(event.target.value)}>
            {!project && <option value="">Select a project</option>}
            {projects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </label>

        <div className="nav-section-label">PLATFORM</div>
        <nav className="nav-list">
          {primary.map((item) => (
            <SidebarLink key={item.to} item={item} />
          ))}
        </nav>

        <div className="nav-section-label nav-section-label--spaced">
          WORKSPACE
        </div>
        <nav className="nav-list">
          {workspace.map((item) => (
            <SidebarLink key={item.to} item={item} />
          ))}
        </nav>

        <div className="sidebar__bottom">
          <div className="ai-card">
            <span className="ai-card__icon">
              <Sparkles size={16} />
            </span>
            <strong>Adaptive testing</strong>
            <p>Explore beyond the happy path.</p>
            <NavLink to="/campaigns">
              View campaigns <span>↗</span>
            </NavLink>
          </div>

          <SidebarLink
            item={{ label: 'Settings', to: '/settings', icon: Settings2 }}
          />

          <button className="nav-link nav-link--button" type="button">
            <CircleHelp size={17} />
            <span>Help &amp; documentation</span>
          </button>

          <div className="profile">
            {user?.avatar_url ? (
              <img
                className="avatar"
                src={user.avatar_url}
                alt={`${displayName}'s avatar`}
              />
            ) : (
              <div className="avatar">{initials}</div>
            )}

            <div className="profile__copy">
              <strong>{displayName}</strong>
              <small>{user?.email || 'Signed in with Google'}</small>
            </div>

            <button
              type="button"
              aria-label="Sign out"
              title="Sign out"
              onClick={() => void handleLogout()}
            >
              <LogOut size={16} />
            </button>
          </div>

          {logoutError && (
            <p role="alert" className="profile__error">
              {logoutError}
            </p>
          )}
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="breadcrumbs">
            <span>Workspace</span>
            <span className="breadcrumbs__slash">/</span>
            <strong>{project?.name ?? 'No project selected'}</strong>
          </div>

          <div className="topbar__actions">
            <span className="demo-indicator">
              <span /> {project ? 'Project connected' : 'Select a project'}
            </span>

            <div className="topbar__divider" />

            <div className="avatar avatar--small">{initials}</div>

            <button
              className="icon-button"
              type="button"
              onClick={() => void handleLogout()}
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut size={17} />
              <span>Sign out</span>
            </button>
          </div>
        </header>

        <main className="main-content">
          <Outlet />
        </main>

        <footer className="app-footer">
          <span>
            <span className="footer-dot" /> System operational
            <span className="footer-separator">·</span> UI foundation
          </span>
          <span>
            IntelAPI <span className="footer-separator">/</span> Preview build
            0.1.0
          </span>
        </footer>
      </div>
    </div>
  )
}

export function AppShell() {
  return <ProjectProvider><AppShellContent /></ProjectProvider>
}
