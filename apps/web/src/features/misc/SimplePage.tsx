import { useState } from 'react'
import { Boxes, Clock3, FolderKanban, Plus, Settings2 } from 'lucide-react'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { Button } from '../../components/ui/Button'
import { EmptyState } from '../../components/ui/EmptyState'

type Kind = 'collections' | 'environments' | 'history' | 'settings'
const config: Record<Kind, { title: string; eyebrow: string; description: string; icon: typeof Boxes; subtitle: string }> = {
  collections: { title: 'Collections', eyebrow: 'REQUEST ORGANIZATION', description: 'Group related requests into reusable collections.', icon: FolderKanban, subtitle: 'Saved request groups' },
  environments: { title: 'Environments', eyebrow: 'CONFIGURATION', description: 'Manage base URLs and environment-specific variables safely.', icon: Boxes, subtitle: 'Environment configurations' },
  history: { title: 'Request History', eyebrow: 'ACTIVITY', description: 'Review previously executed requests and their captured evidence.', icon: Clock3, subtitle: 'Recent request executions' },
  settings: { title: 'Settings', eyebrow: 'WORKSPACE CONFIGURATION', description: 'Configure workspace preferences and integrations.', icon: Settings2, subtitle: 'Workspace settings' },
}
export function SimplePage({ kind }: { kind: Kind }) {
  const item = config[kind]
  const Icon = item.icon
  const [notice, setNotice] = useState(false)
  return <>
    <PageHeader eyebrow={item.eyebrow} title={item.title} description={item.description} actions={kind === 'history' ? undefined : <Button variant="primary" onClick={() => setNotice(true)}><Plus size={15} /> {kind === 'settings' ? 'Configure' : 'Create new'}</Button>} />
    {notice && <div className="notice notice--warning"><span className="notice__icon"><Settings2 size={16} /></span><div><strong>Backend persistence is not connected</strong><p>This action is a UI placeholder. No data has been saved.</p></div><button className="notice__close" onClick={() => setNotice(false)} aria-label="Dismiss">×</button></div>}
    <Panel title={item.subtitle} subtitle="This section is scaffolded for the next implementation milestone">
      <EmptyState title={`No ${kind === 'history' ? 'requests' : kind} yet`} description={kind === 'history' ? 'Executed requests will appear here after the backend execution service is connected.' : 'Create and manage these resources once authentication and persistence are implemented.'} action={<Button onClick={() => setNotice(true)}><Icon size={15} /> Explore setup</Button>} />
    </Panel>
  </>
}