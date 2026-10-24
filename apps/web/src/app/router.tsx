import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppShell } from '../components/layout/AppShell'
import { OverviewPage } from '../features/overview/OverviewPage'
import { WorkspacePage } from '../features/workspace/WorkspacePage'
import { HealthChecksPage } from '../features/health/HealthChecksPage'
import { ExplorerPage } from '../features/explorer/ExplorerPage'
import { CampaignsPage } from '../features/campaigns/CampaignsPage'
import { FindingsPage } from '../features/findings/FindingsPage'
import { SimplePage } from '../features/misc/SimplePage'
import { WorkbenchPage } from '../features/experiments/WorkbenchPage'
import { ResourceManagementPage } from '../features/misc/ResourceManagementPage'

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
      { path: 'workbench', element: <WorkbenchPage /> },
      { path: 'collections', element: <ResourceManagementPage kind="collections" /> },
      { path: 'environments', element: <ResourceManagementPage kind="environments" /> },
      { path: 'history', element: <SimplePage kind="history" /> },
      { path: 'settings', element: <SimplePage kind="settings" /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])
