import { Link } from 'react-router-dom'
import { FileSearch2, ShieldAlert } from 'lucide-react'
import { Button } from '../../components/ui/Button'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'

export function FindingsPage() {
  return <>
    <PageHeader eyebrow="EVIDENCE & ANALYSIS" title="Findings & Evidence" description="Review verified observations and evidence linked to real test runs." />
    <Panel title="No classified findings" subtitle="An unusual HTTP response is evidence to inspect, not automatically a defect.">
      <div className="p-5">
        <ShieldAlert size={20} className="mb-3 text-slate-500" />
        <p className="mt-0 text-sm text-slate-200">There are no persisted findings in this project yet.</p>
        <p className="text-xs text-slate-400">The current build records request status and timing but does not classify contract mismatches or persist response evidence.</p>
        <Link to="/explorer"><Button variant="primary"><FileSearch2 size={15} /> Review an API specification</Button></Link>
      </div>
    </Panel>
  </>
}
