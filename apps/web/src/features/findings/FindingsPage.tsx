import { useMemo, useState } from 'react'
import { Filter, Search, ShieldAlert } from 'lucide-react'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { findings } from '../../lib/demoData'

export function FindingsPage() {
  const [severity, setSeverity] = useState('All')
  const [query, setQuery] = useState('')
  const visible = useMemo(() => findings.filter(f => (severity === 'All' || f.severity === severity) && `${f.title} ${f.endpoint} ${f.category} ${f.id}`.toLowerCase().includes(query.toLowerCase())), [severity, query])
  return <>
    <PageHeader eyebrow="EVIDENCE & ANALYSIS" title="Findings & Evidence" description="Review behavioral signals with traceable observations, context, and provenance." actions={<Button><Filter size={15} /> Export report</Button>} />
    <div className="notice notice--demo"><span className="notice__icon"><ShieldAlert size={16} /></span><div><strong>Illustrative findings</strong><p>These examples are not defects in a real API. The product must classify unusual behavior as an observation until supported by evidence.</p></div></div>
    <div className="metrics-grid metrics-grid--three"><div className="metric-card"><div className="metric-card__top"><span>Open signals</span><ShieldAlert size={16} /></div><div className="metric-card__value">08</div><div className="metric-card__foot"><span className="metric-period">Demo count</span></div></div><div className="metric-card"><div className="metric-card__top"><span>High severity</span><span className="severity-marker severity-marker--high" /></div><div className="metric-card__value">02</div><div className="metric-card__foot"><span className="metric-period">Demo count</span></div></div><div className="metric-card"><div className="metric-card__top"><span>Evidence captured</span><ShieldAlert size={16} /></div><div className="metric-card__value">31</div><div className="metric-card__foot"><span className="metric-period">Demo count</span></div></div></div>
    <Panel title="Findings" subtitle={`${visible.length} matching observations`} action={<div className="search-field"><Search size={15} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search findings..." aria-label="Search findings" /></div>}>
      <div className="filter-toolbar filter-toolbar--inside"><div className="filter-pills">{['All','Critical','High','Medium','Low'].map(s => <button key={s} className={`filter-pill${severity === s ? ' filter-pill--active' : ''}`} onClick={() => setSeverity(s)}>{s}</button>)}</div></div>
      <div className="finding-cards">{visible.map(f => <article className="finding-card" key={f.id}><div className="finding-card__top"><span className={`severity-marker severity-marker--${f.severity.toLowerCase()}`} /><span className="finding-card__id">{f.id}</span><Badge tone={f.severity === 'High' || f.severity === 'Critical' ? 'danger' : f.severity === 'Medium' ? 'warning' : 'neutral'}>{f.severity}</Badge><span className="finding-card__spacer" /><Badge>{f.status}</Badge></div><h3>{f.title}</h3><p>{f.summary}</p><div className="finding-card__meta"><code>{f.endpoint}</code><span>{f.category}</span><span>{f.observedAt}</span></div><div className="finding-card__footer"><span><ShieldAlert size={14} /> Evidence snapshot available in demo</span><Button size="sm" onClick={() => window.alert(`Demo finding ${f.id}: evidence detail view will be implemented with the backend.`)}>View evidence</Button></div></article>)}</div>
      {visible.length === 0 && <div className="table-empty">No findings match the current filters.</div>}
    </Panel>
  </>
}