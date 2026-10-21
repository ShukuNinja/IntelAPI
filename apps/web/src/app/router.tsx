import { ProjectsPage } from '../features/projects/ProjectsPage'
import { Navigate, createBrowserRouter } from 'react-router-dom'
import { AppShell } from '../components/layout/AppShell'
import { CampaignsPage } from '../features/campaigns/CampaignsPage'
import { ExplorerPage } from '../features/explorer/ExplorerPage'
import { FindingsPage } from '../features/findings/FindingsPage'
import { HealthChecksPage } from '../features/health/HealthChecksPage'
import { OverviewPage } from '../features/overview/OverviewPage'
import { SettingsPage } from '../features/misc/SettingsPage'
import { WorkspacePage } from '../features/workspace/WorkspacePage'
import { CollectionsPage, EnvironmentsPage, HistoryPage } from '../features/workspace/WorkspaceResourcePages'
import { LoginPage } from '../features/auth/LoginPage'
import { useAuth } from '../features/auth/AuthContext'

function ProtectedApp() {
  const { status, error, refreshUser } = useAuth()

  if (status === 'loading') {
    return <main style={{ padding: 32 }}>Checking your session…</main>
  }

  if (status === 'error') {
    return (
      <main style={{ padding: 32 }}>
        <h2>Unable to connect to the API</h2>
        <p>{error}</p>
        <button type="button" onClick={() => void refreshUser()}>
          Retry
        </button>
      </main>
    )
  }

  if (status !== 'authenticated') {
    return <Navigate to="/login" replace />
  }

  return <AppShell />
}

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: <ProtectedApp />,
    children: [
      { index: true, element: <OverviewPage /> },
      { path: 'workspace', element: <WorkspacePage /> },
      { path: 'health', element: <HealthChecksPage /> },
      { path: 'explorer', element: <ExplorerPage /> },
      { path: 'campaigns', element: <CampaignsPage /> },
      { path: 'findings', element: <FindingsPage /> },
      { path: 'collections', element: <CollectionsPage /> },
      { path: 'environments', element: <EnvironmentsPage /> },
      { path: 'history', element: <HistoryPage /> },
      { path: 'settings', element: <SettingsPage /> },
      { path: '*', element: <Navigate to="/" replace /> },
      { path: 'projects', element: <ProjectsPage /> },
    ],
  },
])
