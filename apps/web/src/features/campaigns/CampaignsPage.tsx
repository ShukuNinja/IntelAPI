import { Link } from 'react-router-dom'
import { FileSearch2, Send } from 'lucide-react'
import { Button } from '../../components/ui/Button'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'

export function CampaignsPage() {
  return <>
    <PageHeader eyebrow="TEST CAMPAIGNS" title="Campaigns" description="Campaign scheduling and bounded multi-request runs are still being implemented." />
    <Panel title="No campaign runs" subtitle="This workspace currently supports individual requests and deterministic candidate previews.">
      <div className="p-5">
        <p className="mt-0 text-sm text-slate-200">No campaign records are stored, so this page does not show sample runs.</p>
        <p className="text-xs text-slate-400">Use API Explorer to import a contract and inspect generated candidate ideas. Campaign persistence, bounded candidate execution, and feedback policies are not available yet.</p>
        <div className="flex flex-wrap gap-2"><Link to="/explorer"><Button variant="primary"><FileSearch2 size={15} /> Open API Explorer</Button></Link><Link to="/workspace"><Button><Send size={15} /> Open request workspace</Button></Link></div>
      </div>
    </Panel>
  </>
}
