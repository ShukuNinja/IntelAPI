import { ArrowRight, ArrowUpRight, Clock3, FlaskConical, Plus, Sparkles, TrendingUp } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { MethodBadge } from '../../components/ui/MethodBadge'
import { campaigns, findings, healthChecks, metrics } from '../../lib/demoData'

export function OverviewPage() {
  return <>
    <PageHeader eyebrow="MONDAY, OCTOBER 19, 2026" title="Good morning, Jordan" description="Here's what's happening across your API workspace."
      actions={<><Button onClick={() => window.location.assign('/workspace')}><Plus size={16} /> New request</Button><Button variant="primary" onClick={() => window.location.assign('/campaigns')}><FlaskConical size={16} /> Create campaign</Button></>} />
    <div className="notice notice--demo"><span className="notice__icon"><Sparkles size={16} /></span><div><strong>Preview workspace</strong><p>Numbers and endpoint statuses below are illustrative demo data. No real API requests have been executed.</p></div></div>
    <div className="metrics-grid">{metrics.map((metric, i) => <div className="metric-card" key={metric.label}><div className="metric-card__top"><span>{metric.label}</span><span className={`metric-icon metric-icon--${i}`}><TrendingUp size={16} /></span></div><div className="metric-card__value">{metric.value}</div><div className="metric-card__foot"><span className={`metric-change metric-change--${metric.tone ?? 'neutral'}`}>{metric.change}</span><span className="metric-period">workspace total</span></div></div>)}</div>
    <div className="dashboard-grid">
      <Panel title="Endpoint health" subtitle="Latest recorded checks (demo)" action={<Link className="text-link" to="/health">View all <ArrowRight size={14} /></Link>}>
        <div className="table-wrap"><table><thead><tr><th>ENDPOINT</th><th>STATUS</th><th>LATENCY</th><th>LAST CHECKED</th></tr></thead><tbody>{healthChecks.slice(0, 3).map((item) => <tr key={item.id}><td><div className="endpoint-cell"><MethodBadge method={item.method} /><span>{item.name}<small>{item.endpoint}</small></span></div></td><td><Badge tone={item.status === 'Healthy' ? 'success' : item.status === 'Degraded' ? 'warning' : 'neutral'}>{item.status}</Badge></td><td className="tabular">{item.latency ? `${item.latency} ms` : '—'}</td><td className="muted-cell">{item.lastChecked}</td></tr>)}</tbody></table></div>
      </Panel>
      <Panel title="Recent findings" subtitle="Signals requiring attention" action={<Link className="text-link" to="/findings">All findings <ArrowRight size={14} /></Link>}>
        <div className="finding-list">{findings.slice(0, 3).map((item) => <Link to="/findings" className="finding-row" key={item.id}><span className={`severity-marker severity-marker--${item.severity.toLowerCase()}`} /><span className="finding-row__copy"><strong>{item.title}</strong><small>{item.id} <span>·</span> {item.endpoint}</small></span><ArrowUpRight size={15} className="muted-icon" /></Link>)}</div>
      </Panel>
      <Panel title="Campaign activity" subtitle="Exploration and validation runs" action={<Link className="text-link" to="/campaigns">View campaigns <ArrowRight size={14} /></Link>} className="span-2">
        <div className="campaign-list">{campaigns.slice(0, 2).map((item) => <div className="campaign-row" key={item.id}><span className="campaign-icon"><FlaskConical size={17} /></span><div className="campaign-row__copy"><strong>{item.name}</strong><small>{item.target} <span>·</span> Updated {item.updatedAt}</small></div><div className="campaign-row__stats"><strong>{item.tests}</strong><small>tests</small></div><div className="campaign-row__stats"><strong>{item.findings}</strong><small>signals</small></div><Badge tone={item.status === 'Running' ? 'info' : 'success'}>{item.status}</Badge></div>)}</div>
      </Panel>
      <Panel title="Quick start" subtitle="Continue building your workspace" className="quick-start">
        <Link className="quick-action" to="/explorer"><span className="quick-action__icon"><Clock3 size={17} /></span><span><strong>Import an API specification</strong><small>Map endpoints from an OpenAPI document.</small></span><ArrowRight size={15} /></Link>
        <Link className="quick-action" to="/workspace"><span className="quick-action__icon"><Plus size={17} /></span><span><strong>Send your first request</strong><small>Build a request in the API workspace.</small></span><ArrowRight size={15} /></Link>
      </Panel>
    </div>
  </>
}