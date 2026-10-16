import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppShell } from '../components/layout/AppShell'
import { OverviewPage } from '../features/overview/OverviewPage'
import { WorkspacePage } from '../features/workspace/WorkspacePage'
import { HealthChecksPage } from '../features/health/HealthChecksPage'
import { ExplorerPage } from '../features/explorer/ExplorerPage'
import { CampaignsPage } from '../features/campaigns/CampaignsPage'
import { FindingsPage } from '../features/findings/FindingsPage'
import { SimplePage } from '../features/misc/SimplePage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <OverviewPage /> },
      { path: 'workspace', element: <WorkspacePage /> },
      { path: 'health', element: <HealthChecksPage /> },
      { path: 'explorer', element: <ExplorerPage /> },
      { path: 'campaigns', element: <CampaignsPage /> },
      { path: 'findings', element: <FindingsPage /> },
      { path: 'collections', element: <SimplePage kind="collections" /> },
      { path: 'environments', element: <SimplePage kind="environments" /> },
      { path: 'history', element: <SimplePage kind="history" /> },
      { path: 'settings', element: <SimplePage kind="settings" /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])