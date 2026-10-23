import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { FileSearch2, RefreshCw, ShieldAlert } from 'lucide-react'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { apiRequest } from '../../lib/apiClient'

type Project = { id: string; name: string }
type Finding = { id: string; execution_report_id: string; candidate_id: string; created_at: string | null; operation: { method?: string; path?: string }; execution: { status_code?: number | null }; kind: string; details: Record<string, unknown>; classification: 'untriaged' | 'confirmed' | 'false_positive' | 'accepted'; notes: string | null; evidence_key: string }

export function FindingsPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [findings, setFindings] = useState<Finding[]>([])
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState('')

  useEffect(() => {
    void apiRequest<Project[]>('/v1/projects').then(items => {
      setProjects(items)
      setProjectId(current => current || items[0]?.id || '')
    }).catch(cause => setError(cause instanceof Error ? cause.message : 'Unable to load projects.'))
  }, [])

  const refresh = useCallback(async () => {
    if (!projectId) { setFindings([]); return }
    setError('')
    try { setFindings(await apiRequest<Finding[]>(`/v1/projects/${projectId}/findings`)) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load findings.') }
  }, [projectId])

  useEffect(() => { void refresh() }, [refresh])

  async function classify(finding: Finding, classification: Finding['classification']) {
    setBusyId(finding.id); setError('')
    try {
      await apiRequest(`/v1/projects/${projectId}/findings/${finding.execution_report_id}/${encodeURIComponent(finding.evidence_key)}`, {
        method: 'PUT', body: JSON.stringify({ classification, notes: notes[finding.id] ?? finding.notes }),
      })
      await refresh()
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to save finding triage.') }
    finally { setBusyId('') }
  }

  return <>
    <PageHeader eyebrow="EVIDENCE & ANALYSIS" title="Findings & Evidence" description="Review real execution observations and record a human triage decision." />
    <Panel title="Observation review" subtitle="Contract mismatches and failed assertions are evidence to review; the system never labels them defects automatically.">
      <div className="space-y-4 p-4">
        <div className="flex flex-wrap items-center gap-2"><label className="text-xs text-slate-300">Project<select className="ml-2 rounded border border-slate-700 bg-slate-900 px-3 py-2" value={projectId} onChange={event => setProjectId(event.target.value)}><option value="">Select project…</option>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label><Button size="sm" onClick={() => void refresh()}><RefreshCw size={14} /> Refresh</Button></div>
        {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}
        {findings.length === 0 ? <div className="rounded border border-slate-800 p-5"><ShieldAlert size={20} className="mb-3 text-slate-500" /><p className="mt-0 text-sm text-slate-200">No execution observations to triage.</p><p className="text-xs text-slate-400">Run an API candidate with a failed assertion or a contract observation to create reviewable evidence.</p><Link to="/explorer"><Button variant="primary"><FileSearch2 size={15} /> Review an API specification</Button></Link></div> : <div className="space-y-3">{findings.map(finding => <article key={finding.id} className="rounded-lg border border-slate-800 bg-slate-950/40 p-4"><div className="flex flex-wrap items-center gap-2"><Badge tone={finding.classification === 'confirmed' ? 'warning' : finding.classification === 'untriaged' ? 'neutral' : 'success'}>{finding.classification.replace('_', ' ')}</Badge><Badge>{finding.kind}</Badge><span className="font-mono text-xs text-slate-200">{finding.operation.method} {finding.operation.path}</span><span className="ml-auto text-[11px] text-slate-500">HTTP {finding.execution.status_code ?? 'no response'} · {finding.created_at ? new Date(finding.created_at).toLocaleString() : ''}</span></div><pre className="mt-3 overflow-auto rounded bg-slate-950 p-3 text-[11px] text-slate-300">{JSON.stringify(finding.details, null, 2)}</pre><input aria-label="Triage notes" className="mb-3 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-100" placeholder="Optional review note" value={notes[finding.id] ?? finding.notes ?? ''} onChange={event => setNotes(current => ({ ...current, [finding.id]: event.target.value }))} /><div className="flex flex-wrap gap-2"><Button size="sm" disabled={busyId === finding.id} onClick={() => void classify(finding, 'confirmed')}>Confirm defect</Button><Button size="sm" disabled={busyId === finding.id} onClick={() => void classify(finding, 'false_positive')}>False positive</Button><Button size="sm" disabled={busyId === finding.id} onClick={() => void classify(finding, 'accepted')}>Accept risk</Button></div></article>)}</div>}
      </div>
    </Panel>
  </>
}
