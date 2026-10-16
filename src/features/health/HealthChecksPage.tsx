import { useState } from 'react'
import { Activity, Plus, RefreshCw } from 'lucide-react'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { MethodBadge } from '../../components/ui/MethodBadge'
import { healthChecks } from '../../lib/demoData'

export function HealthChecksPage() {
  const [refreshed, setRefreshed] = useState(false)
  return <>
    <PageHeader eyebrow="OBSERVABILITY" title="Health Checks" description="Review endpoint reachability and recorded response characteristics." actions={<><Button onClick={() => setRefreshed(true)}><RefreshCw size={15} /> Refresh view</Button><Button variant="primary" onClick={() => setRefreshed(true)}><Plus size={15} /> Add check</Button></>} />
    {refreshed && <div className="notice notice--warning"><span className="notice__icon"><Activity size={16} /></span><div><strong>Demo view refreshed</strong><p>These are static examples. Refreshing does not execute a health check.</p></div><button className="notice__close" onClick={() => setRefreshed(false)} aria-label="Dismiss">×</button></div>}
    <div className="metrics-grid metrics-grid--three"><div className="metric-card"><div className="metric-card__top"><span>Configured checks</span><Activity size={16} /></div><div className="metric-card__value">04</div><div className="metric-card__foot"><span className="metric-period">Demo configuration</span></div></div><div className="metric-card"><div className="metric-card__top"><span>Healthy</span><span className="status-dot status-dot--green" /></div><div className="metric-card__value">02</div><div className="metric-card__foot"><span className="metric-period">Illustrative state</span></div></div><div className="metric-card"><div className="metric-card__top"><span>Needs attention</span><span className="status-dot status-dot--amber" /></div><div className="metric-card__value">01</div><div className="metric-card__foot"><span className="metric-period">Illustrative state</span></div></div></div>
    <Panel title="Configured endpoint checks" subtitle="Example configuration and simulated status">
      <div className="table-wrap"><table><thead><tr><th>ENDPOINT</th><th>STATUS</th><th>LATENCY</th><th>LAST CHECKED</th><th>ACTION</th></tr></thead><tbody>{healthChecks.map(check => <tr key={check.id}><td><div className="endpoint-cell"><MethodBadge method={check.method} /><span>{check.name}<small>{check.endpoint}</small></span></div></td><td><Badge tone={check.status === 'Healthy' ? 'success' : check.status === 'Degraded' ? 'warning' : 'neutral'}>{check.status}</Badge></td><td className="tabular">{check.latency === null ? '—' : `${check.latency} ms`}</td><td className="muted-cell">{check.lastChecked}</td><td><Button size="sm" onClick={() => setRefreshed(true)}>Run check</Button></td></tr>)}</tbody></table></div>
    </Panel>
    <div className="notice notice--info"><span className="notice__icon"><Activity size={16} /></span><div><strong>Health-check semantics</strong><p>The backend will distinguish reachability, timeout, HTTP status, and application assertions. This screen currently displays illustrative data only.</p></div></div>
  </>
}