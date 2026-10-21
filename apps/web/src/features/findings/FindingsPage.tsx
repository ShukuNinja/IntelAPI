import { useCallback, useEffect, useMemo, useState } from 'react'
import { Download, Search, ShieldAlert } from 'lucide-react'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { EmptyState } from '../../components/ui/EmptyState'
import { useProject } from '../projects/ProjectContext'
import { findingsService, type EvidenceReference, type Finding } from './findingsService'

const severityTone = (value: string) => value === 'critical' || value === 'high' ? 'danger' : value === 'medium' ? 'warning' : 'neutral'

export function FindingsPage() {
  const { project } = useProject()
  const [items, setItems] = useState<Finding[]>([])
  const [expanded, setExpanded] = useState<Record<string, EvidenceReference[] | null>>({})
  const [severity, setSeverity] = useState('All')
  const [status, setStatus] = useState('All')
  const [query, setQuery] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState('')

  const refresh = useCallback(async () => {
    if (!project) { setItems([]); return }
    try { const result = await findingsService.list(project.id); setItems(result.items); setError(null) }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to load findings.') }
  }, [project])
  useEffect(() => { void refresh() }, [refresh])

  const visible = useMemo(() => items.filter(finding => {
    const effectiveSeverity = finding.user_severity ?? finding.machine_severity
    return (severity === 'All' || effectiveSeverity.toLowerCase() === severity.toLowerCase())
      && (status === 'All' || finding.user_status === status.toLowerCase())
      && `${finding.title} ${finding.summary} ${finding.classification} ${finding.id}`.toLowerCase().includes(query.toLowerCase())
  }), [items, severity, status, query])
  const severityCount = (value: string) => items.filter(item => (item.user_severity ?? item.machine_severity).toLowerCase() === value.toLowerCase()).length

  async function showEvidence(finding: Finding) {
    if (expanded[finding.id] !== undefined) { setExpanded(current => { const next = { ...current }; delete next[finding.id]; return next }); return }
    try { setExpanded(current => ({ ...current, [finding.id]: null })); const result = await findingsService.evidence(finding.id); setExpanded(current => ({ ...current, [finding.id]: result })) }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to load finding evidence.') }
  }
  async function update(finding: Finding, patch: Partial<Pick<Finding, 'user_status' | 'user_severity' | 'triage_note'>>) {
    setBusyId(finding.id)
    try { const updated = await findingsService.update(finding.id, { user_status: patch.user_status ?? finding.user_status, user_severity: patch.user_severity ?? finding.user_severity, triage_note: patch.triage_note ?? finding.triage_note }); setItems(current => current.map(item => item.id === updated.id ? updated : item)) }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to save triage changes.') }
    finally { setBusyId('') }
  }
  function exportFindings() {
    const blob = new Blob([JSON.stringify(visible, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a'); link.href = url; link.download = `intelapi-findings-${project?.id ?? 'project'}.json`; link.click(); URL.revokeObjectURL(url)
  }

  return <>
    <PageHeader eyebrow="EVIDENCE & ANALYSIS" title="Findings & Evidence" description="Review potential issues from explicit assertion mismatches, inspect their sources, and manage triage." actions={<Button onClick={exportFindings} disabled={!visible.length}><Download size={15} /> Export JSON</Button>} />
    {error && <div className="notice notice--warning"><span className="notice__icon"><ShieldAlert size={16} /></span><div><strong>Request failed</strong><p>{error}</p></div><button className="notice__close" onClick={() => setError(null)} aria-label="Dismiss">×</button></div>}
    <div className="metrics-grid metrics-grid--three"><div className="metric-card"><div className="metric-card__top"><span>Open potential findings</span><ShieldAlert size={16} /></div><div className="metric-card__value">{items.filter(item => item.user_status === 'open').length}</div><div className="metric-card__foot"><span className="metric-period">Persisted for this project</span></div></div><div className="metric-card"><div className="metric-card__top"><span>High severity</span><span className="severity-marker severity-marker--high" /></div><div className="metric-card__value">{severityCount('high') + severityCount('critical')}</div><div className="metric-card__foot"><span className="metric-period">Machine or triaged severity</span></div></div><div className="metric-card"><div className="metric-card__top"><span>Evidence references</span><ShieldAlert size={16} /></div><div className="metric-card__value">{items.reduce((total, finding) => total + finding.evidence_count, 0)}</div><div className="metric-card__foot"><span className="metric-period">Traceable source records</span></div></div></div>
    <Panel title="Potential findings" subtitle={`${visible.length} matching record${visible.length === 1 ? '' : 's'}`} action={<div className="search-field"><Search size={15} /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search findings…" aria-label="Search findings" /></div>}>
      <div className="filter-toolbar filter-toolbar--inside"><div className="filter-pills">{['All','Critical','High','Medium','Low'].map(value => <button key={value} className={`filter-pill${severity === value ? ' filter-pill--active' : ''}`} onClick={() => setSeverity(value)}>{value}</button>)}</div><select aria-label="Finding status filter" value={status} onChange={event => setStatus(event.target.value)}><option>All</option>{['open','confirmed','accepted','resolved','false_positive'].map(value => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}</select></div>
      {visible.length ? <div className="finding-cards">{visible.map(finding => <article className="finding-card" key={finding.id}><div className="finding-card__top"><span className={`severity-marker severity-marker--${(finding.user_severity ?? finding.machine_severity).toLowerCase()}`} /><span className="finding-card__id">{finding.id.slice(0, 8)}</span><Badge tone={severityTone(finding.user_severity ?? finding.machine_severity)}>{finding.user_severity ?? finding.machine_severity}</Badge><span className="finding-card__spacer" /><Badge>{finding.user_status.replaceAll('_', ' ')}</Badge></div><h3>{finding.title}</h3><p>{finding.summary}</p><div className="finding-card__meta"><span>{finding.classification.replaceAll('_', ' ')}</span><span>Machine severity: {finding.machine_severity}</span><span>Confidence: {finding.confidence === null ? '—' : `${Math.round(finding.confidence * 100)}%`}</span><span>{new Date(finding.created_at).toLocaleString()}</span></div><div className="resource-form"><select aria-label="Triage status" value={finding.user_status} disabled={busyId === finding.id} onChange={event => void update(finding, { user_status: event.target.value })}>{['open','confirmed','accepted','resolved','false_positive'].map(value => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}</select><select aria-label="Triage severity" value={finding.user_severity ?? ''} disabled={busyId === finding.id} onChange={event => void update(finding, { user_severity: event.target.value || null })}><option value="">Use machine severity</option>{['low','medium','high','critical'].map(value => <option key={value} value={value}>{value}</option>)}</select><Button size="sm" onClick={() => void showEvidence(finding)}>Evidence ({finding.evidence_count})</Button></div>{finding.triage_note && <small>Triage note: {finding.triage_note}</small>}{expanded[finding.id] !== undefined && <div className="resource-list">{expanded[finding.id] === null ? <small>Loading evidence…</small> : expanded[finding.id]?.map(evidence => <article className="environment-card" key={evidence.id}><Badge>{evidence.provenance}</Badge><div className="environment-card__body"><strong>{evidence.evidence_type.replaceAll('_', ' ')}</strong><p>{evidence.excerpt}</p><small>{evidence.execution_id ? `Execution ${evidence.execution_id}` : ''}{evidence.assertion_result_id ? ` · Assertion ${evidence.assertion_result_id}` : ''}</small></div></article>)}</div>}</article>)}</div> : <EmptyState title="No findings match" description={items.length ? 'Adjust the current filters.' : 'Failed configured health assertions will create reviewable, evidence-backed potential findings.'} />}
    </Panel>
  </>
}
