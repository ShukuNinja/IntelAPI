import { useState } from 'react'
import { FlaskConical, Plus, Search, SlidersHorizontal } from 'lucide-react'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { EmptyState } from '../../components/ui/EmptyState'
import { campaigns as initialCampaigns } from '../../lib/demoData'

export function CampaignsPage() {
  const [filter, setFilter] = useState('All')
  const [showCreate, setShowCreate] = useState(false)
  const [name, setName] = useState('')
  const [items, setItems] = useState(initialCampaigns)
  const visible = items.filter(c => filter === 'All' || c.status === filter)
  function createCampaign() {
    const trimmed = name.trim()
    if (!trimmed) return
    setItems(current => [{ id: `CMP-${String(9 + current.length).padStart(3, '0')}`, name: trimmed, target: 'No target selected', status: 'Draft', tests: 0, findings: 0, updatedAt: 'Just now' }, ...current])
    setName('')
    setShowCreate(false)
  }
  return <>
    <PageHeader eyebrow="ADAPTIVE TESTING" title="Test Campaigns" description="Plan bounded test runs, explore behavior, and preserve evidence for follow-up." actions={<Button variant="primary" onClick={() => setShowCreate(v => !v)}><Plus size={15} /> New campaign</Button>} />
    {showCreate && <Panel title="Create a draft campaign" subtitle="Local UI state only; this is not persisted to the backend"><div className="create-form"><label htmlFor="campaign-name">Campaign name</label><input id="campaign-name" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Orders boundary exploration" /><div className="form-actions"><Button onClick={() => setShowCreate(false)}>Cancel</Button><Button variant="primary" onClick={createCampaign} disabled={!name.trim()}>Create draft</Button></div></div></Panel>}
    <div className="filter-toolbar"><div className="filter-pills">{['All','Running','Draft','Completed','Paused'].map(s => <button key={s} className={`filter-pill${filter === s ? ' filter-pill--active' : ''}`} onClick={() => setFilter(s)}>{s}</button>)}</div><Button size="sm"><SlidersHorizontal size={14} /> Filters</Button></div>
    <Panel title="Campaigns" subtitle={`${visible.length} campaign${visible.length === 1 ? '' : 's'} shown`} action={<div className="search-field"><Search size={15} /><input placeholder="Search campaigns..." aria-label="Search campaigns" /></div>}>
      {visible.length ? <div className="table-wrap"><table><thead><tr><th>CAMPAIGN</th><th>STATUS</th><th>TESTS</th><th>FINDINGS</th><th>LAST UPDATED</th></tr></thead><tbody>{visible.map(c => <tr key={c.id}><td><div className="campaign-table-name"><span className="campaign-icon"><FlaskConical size={16} /></span><span><strong>{c.name}</strong><small>{c.id} <span>·</span> {c.target}</small></span></div></td><td><Badge tone={c.status === 'Running' ? 'info' : c.status === 'Completed' ? 'success' : 'neutral'}>{c.status}</Badge></td><td className="tabular">{c.tests}</td><td className="tabular">{c.findings}</td><td className="muted-cell">{c.updatedAt}</td></tr>)}</tbody></table></div> : <EmptyState title="No campaigns in this state" description="Create a campaign draft or choose a different filter." action={<Button onClick={() => setFilter('All')}>Show all campaigns</Button>} />}
    </Panel>
    <div className="notice notice--info"><span className="notice__icon"><FlaskConical size={16} /></span><div><strong>Campaign execution safeguards</strong><p>Campaigns will enforce request budgets, iteration limits, deadlines, timeouts, and target authorization before execution. Those controls are not active in this UI-only stage.</p></div></div>
  </>
}