import { useEffect, useMemo, useState, type FormEvent } from 'react'
import type { FocusEvent, MouseEvent } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  Activity, Boxes, Clock3, Code2, Command, FileSearch2, FolderPlus,
  FlaskConical, FolderKanban, LayoutDashboard, Settings2, ShieldCheck,
  Sparkles, Waves, FlaskConical as ResearchIcon, type LucideIcon,
} from 'lucide-react'
import { apiRequest } from '../../lib/apiClient'
import { ProjectWorkspaceContext, type Project } from '../../features/projects/ProjectWorkspaceContext'

type NavItem = { label: string; to: string; icon: LucideIcon }
const primary: NavItem[] = [
  { label: 'Overview', to: '/', icon: LayoutDashboard },
  { label: 'API Workspace', to: '/workspace', icon: Code2 },
  { label: 'Health Checks', to: '/health', icon: Activity },
  { label: 'API Explorer', to: '/explorer', icon: FileSearch2 },
  { label: 'Test Campaigns', to: '/campaigns', icon: FlaskConical },
  { label: 'Findings & Evidence', to: '/findings', icon: ShieldCheck },
  { label: 'Experimental Workbench', to: '/workbench', icon: ResearchIcon },
]
const workspace: NavItem[] = [
  { label: 'Collections', to: '/collections', icon: FolderKanban },
  { label: 'Environments', to: '/environments', icon: Boxes },
  { label: 'Request History', to: '/history', icon: Clock3 },
]

function SidebarLink({ item }: { item: NavItem }) {
  const Icon = item.icon
  const [tooltip, setTooltip] = useState<{ left: number; top: number } | null>(null)
  const tooltipId = `nav-tooltip-${item.to.replace(/[^a-z0-9]/gi, '-')}`
  const placeAtPointer = (event: MouseEvent<HTMLAnchorElement>) => setTooltip({
    left: Math.min(event.clientX + 14, window.innerWidth - 180),
    top: Math.min(event.clientY + 12, window.innerHeight - 44),
  })
  const placeAtFocus = (event: FocusEvent<HTMLAnchorElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect()
    setTooltip({ left: bounds.right + 12, top: bounds.top + (bounds.height - 30) / 2 })
  }
  return <>
    <NavLink to={item.to} end={item.to === '/'} aria-label={item.label} aria-describedby={tooltip ? tooltipId : undefined} data-label={item.label} className={({ isActive }) => `nav-link${isActive ? ' nav-link--active' : ''}`} onMouseEnter={placeAtPointer} onMouseMove={placeAtPointer} onMouseLeave={() => setTooltip(null)} onFocus={placeAtFocus} onBlur={() => setTooltip(null)}>
      <Icon size={17} strokeWidth={1.8} /><span>{item.label}</span>
    </NavLink>
    {tooltip && <span id={tooltipId} role="tooltip" className="nav-tooltip" style={{ left: tooltip.left, top: tooltip.top }}>{item.label}</span>}
  </>
}

export function AppShell() {
  const [projects, setProjects] = useState<Project[]>([])
  const [activeProjectId, setActiveProjectIdState] = useState('')
  const [loadingProjects, setLoadingProjects] = useState(true)
  const [projectError, setProjectError] = useState('')
  const [showProjectForm, setShowProjectForm] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [creatingProject, setCreatingProject] = useState(false)

  const activeProject = useMemo(() => projects.find(project => project.id === activeProjectId) ?? null, [projects, activeProjectId])
  const setActiveProjectId = (projectId: string) => {
    setActiveProjectIdState(projectId)
    if (projectId) window.localStorage.setItem('intelapi.activeProjectId', projectId)
    else window.localStorage.removeItem('intelapi.activeProjectId')
  }

  useEffect(() => {
    let current = true
    void apiRequest<Project[]>('/v1/projects').then(items => {
      if (!current) return
      setProjects(items)
      const savedId = window.localStorage.getItem('intelapi.activeProjectId')
      const selectedId = items.find(project => project.id === savedId)?.id ?? items[0]?.id ?? ''
      setActiveProjectIdState(selectedId)
      if (selectedId) window.localStorage.setItem('intelapi.activeProjectId', selectedId)
    }).catch(cause => {
      if (current) setProjectError(cause instanceof Error ? cause.message : 'Unable to load projects.')
    }).finally(() => { if (current) setLoadingProjects(false) })
    return () => { current = false }
  }, [])

  async function createProject(name: string) {
    const trimmedName = name.trim()
    if (!trimmedName) throw new Error('Enter a project name.')
    const project = await apiRequest<Project>('/v1/projects', {
      method: 'POST',
      body: JSON.stringify({ name: trimmedName }),
    })
    setProjects(current => [...current, project])
    setActiveProjectId(project.id)
    setProjectError('')
    setShowProjectForm(false)
    setNewProjectName('')
    return project
  }

  async function submitProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setCreatingProject(true)
    setProjectError('')
    try { await createProject(newProjectName) }
    catch (cause) { setProjectError(cause instanceof Error ? cause.message : 'Unable to create project.') }
    finally { setCreatingProject(false) }
  }

  const projectWorkspace = { projects, activeProjectId, setActiveProjectId, createProject, loadingProjects, projectError }

  return (
    <ProjectWorkspaceContext.Provider value={projectWorkspace}>
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink to="/" className="brand">
          <span className="brand__mark"><Waves size={21} /></span>
          <span className="brand__copy"><strong>Intel<span>API</span></strong><small>API INTELLIGENCE</small></span>
        </NavLink>
        <div className="project-switcher">
          <span className="project-switcher__icon"><Command size={16} /></span>
          <span className="project-switcher__copy"><strong>Active project</strong><small>Switch workspace</small></span>
          <select aria-label="Active project" className="project-switcher__select" value={activeProjectId} onChange={event => setActiveProjectId(event.target.value)} disabled={loadingProjects}>
            <option value="">{loadingProjects ? 'Loading…' : 'Select project'}</option>
            {projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
          <button type="button" className="project-switcher__add" aria-label="Create a new project" title="Create a new project" onClick={() => { setShowProjectForm(open => !open); setProjectError('') }}><FolderPlus size={15} /></button>
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
          <div className="breadcrumbs"><span>Workspace</span><span className="breadcrumbs__slash">/</span><strong>{activeProject?.name ?? 'No project selected'}</strong></div>
          <div className="topbar__actions">
            <select aria-label="Active project" className="project-switcher__select" value={activeProjectId} onChange={event => setActiveProjectId(event.target.value)} disabled={loadingProjects}>
              <option value="">{loadingProjects ? 'Loading project…' : 'Select project'}</option>
              {projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
            <button type="button" className="project-switcher__add" aria-label="Create a new project" title="Create a new project" onClick={() => { setShowProjectForm(open => !open); setProjectError('') }}><FolderPlus size={15} /></button>
            <span className="demo-indicator"><span /> Single-user mode</span>
            <div className="avatar avatar--small">LW</div>
          </div>
        </header>
        {showProjectForm && <form className="project-create-form" onSubmit={event => void submitProject(event)}><label htmlFor="new-project-name">Create a new project</label><input id="new-project-name" value={newProjectName} maxLength={120} onChange={event => setNewProjectName(event.target.value)} placeholder="e.g. Payments API" autoFocus /><div className="project-create-form__actions"><button type="submit" disabled={creatingProject || !newProjectName.trim()}>{creatingProject ? 'Creating…' : 'Create project'}</button><button type="button" onClick={() => { setShowProjectForm(false); setNewProjectName('') }}>Cancel</button></div>{projectError && <p role="alert">{projectError}</p>}</form>}
        <main className="main-content">{projectError && !showProjectForm && <p role="alert" className="workspace-error">{projectError}</p>}<Outlet /></main>
        <footer className="app-footer"><span>Local single-user workspace</span><span>IntelAPI <span className="footer-separator">/</span> 0.1.0</span></footer>
      </div>
    </div>
    </ProjectWorkspaceContext.Provider>
  )
}
