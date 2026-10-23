import { Link } from 'react-router-dom'
import { Activity, Send } from 'lucide-react'
import { Button } from '../../components/ui/Button'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'

export function HealthChecksPage() {
  return <>
    <PageHeader eyebrow="OBSERVABILITY" title="Health Checks" description="Run repeatable endpoint checks and review their latest assertions." />
    <Panel title="No configured health checks" subtitle="Health-check definitions and assertion runs have not been connected to persistence yet.">
      <div className="p-5">
        <Activity size={20} className="mb-3 text-slate-500" />
        <p className="mt-0 text-sm text-slate-200">This page has no real check records to display.</p>
        <p className="text-xs text-slate-400">You can send a bounded manual request from the API Workspace. The response is recorded as request history and is not classified as a health check.</p>
        <Link to="/workspace"><Button variant="primary"><Send size={15} /> Open request workspace</Button></Link>
      </div>
    </Panel>
  </>
}
