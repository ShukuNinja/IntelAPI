import { useEffect, useMemo, useState } from 'react'
import { Database, Download, FileSearch2, FolderPlus, Search, UploadCloud } from 'lucide-react'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { MethodBadge } from '../../components/ui/MethodBadge'
import { apiDownload, apiRequest } from '../../lib/apiClient'

type Operation = { id: string; method: string; path: string; summary: string; description: string; tags: string[]; parameters: unknown[]; request_body: Record<string, unknown> }
type ParsedSpec = { specification: { title: string; version: string }; operations: Operation[] }
type Candidate = { id: string; kind: string; reason: string; mutation: Record<string, unknown>; validation_status: string }
type GenerationReport = { id: string; project_id: string; specification_id: string; created_at: string; policy_version: string; specification: { title: string; version: string; content_hash: string }; summary: { operation_count: number; candidate_count: number; endpoints_with_candidates: number; truncated: boolean }; endpoints: { operation: Operation; candidate_count: number; candidates: Candidate[] }[] }
type Project = { id: string; name: string; description: string | null }
type SavedSpecification = { id: string; title: string; version: string; content_hash: string; created_at: string; operation_count: number }
type SavedSpecificationDetail = { id: string; title: string; version: string; source_format: 'json' | 'yaml'; document: Record<string, unknown>; operations: Operation[] }
type SavedReport = { id: string; specification_id: string; policy_version: string; candidate_count: number; operation_count: number; created_at: string }

export function ExplorerPage() {
  const [source, setSource] = useState('')
  const [sourceFormat, setSourceFormat] = useState<'json' | 'yaml'>('json')
  const [filter, setFilter] = useState('')
  const [parsed, setParsed] = useState<ParsedSpec | null>(null)
  const [selected, setSelected] = useState<Operation | null>(null)
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [report, setReport] = useState<GenerationReport | null>(null)
  const [persistedSpecId, setPersistedSpecId] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [projectName, setProjectName] = useState('')
  const [savedSpecs, setSavedSpecs] = useState<SavedSpecification[]>([])
  const [savedReports, setSavedReports] = useState<SavedReport[]>([])
  const [saveMessage, setSaveMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const visible = useMemo(() => parsed?.operations.filter(op => `${op.method} ${op.path} ${op.summary} ${op.tags.join(' ')}`.toLowerCase().includes(filter.toLowerCase())) ?? [], [parsed, filter])

  useEffect(() => {
    void apiRequest<Project[]>('/v1/projects').then(items => {
      setProjects(items)
      if (items[0]) setProjectId(items[0].id)
    }).catch(cause => setError(cause instanceof Error ? cause.message : 'Unable to load projects.'))
  }, [])

  useEffect(() => {
    if (!projectId) { setSavedSpecs([]); setSavedReports([]); return }
    void Promise.all([
      apiRequest<SavedSpecification[]>(`/v1/projects/${projectId}/specifications`),
      apiRequest<SavedReport[]>(`/v1/projects/${projectId}/generation-reports`),
    ]).then(([specs, reports]) => { setSavedSpecs(specs); setSavedReports(reports) })
      .catch(cause => setError(cause instanceof Error ? cause.message : 'Unable to load saved specifications.'))
  }, [projectId])

  async function createProject() {
    if (!projectName.trim()) return
    setBusy(true); setError('')
    try {
      const project = await apiRequest<Project>('/v1/projects', { method: 'POST', body: JSON.stringify({ name: projectName.trim() }) })
      setProjects(current => [...current, project]); setProjectId(project.id); setProjectName('')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to create project.') }
    finally { setBusy(false) }
  }

  async function saveSpecification() {
    if (!parsed || !projectId) return
    setSaving(true); setError(''); setSaveMessage('')
    try {
      const imported = await apiRequest<{ id: string; created: boolean; title: string; operations: Operation[] }>(`/v1/projects/${projectId}/specifications/import`, {
        method: 'POST', body: JSON.stringify({ content: source, source_format: sourceFormat }),
      })
      setPersistedSpecId(imported.id)
      setSaveMessage(imported.created ? 'Specification saved to this project.' : 'This specification is already saved in this project.')
      setSavedSpecs(await apiRequest<SavedSpecification[]>(`/v1/projects/${projectId}/specifications`))
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to save specification.') }
    finally { setSaving(false) }
  }

  async function openSavedSpecification(specificationId: string) {
    if (!projectId) return
    setError('')
    try {
      const saved = await apiRequest<SavedSpecificationDetail>(`/v1/projects/${projectId}/specifications/${specificationId}`)
      setParsed({ specification: { title: saved.title, version: saved.version }, operations: saved.operations })
      setSource(JSON.stringify(saved.document, null, 2)); setSourceFormat('json')
      setPersistedSpecId(saved.id)
      setSelected(null); setReport(null); setCandidates([]); setSaveMessage('Loaded from the selected project.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load saved specification.') }
  }

  async function parse(text = source, format = sourceFormat) {
    setBusy(true); setError(''); setCandidates([]); setReport(null); setPersistedSpecId('')
    try {
      const result = await apiRequest<ParsedSpec>('/v1/specifications/parse', { method: 'POST', body: JSON.stringify({ content: text, source_format: format }) })
      setParsed(result); setSelected(null)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to parse this specification.') }
    finally { setBusy(false) }
  }

  async function preview(operation: Operation) {
    setSelected(operation); setError('')
    try {
      const result = await apiRequest<{ candidates: Candidate[] }>('/v1/specifications/candidates/preview', { method: 'POST', body: JSON.stringify({ operation }) })
      setCandidates(result.candidates)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to preview candidates.') }
  }

  async function generateReport() {
    if (!parsed || parsed.operations.length > 100 || !persistedSpecId || !projectId) {
      setError('Save this specification to the selected project before generating a persistent report.')
      return
    }
    setError('')
    try {
      const result = await apiRequest<GenerationReport>(`/v1/projects/${projectId}/specifications/${persistedSpecId}/generation-reports`, { method: 'POST', body: JSON.stringify({ per_operation_limit: 20 }) })
      setReport(result)
      setSavedReports(await apiRequest<SavedReport[]>(`/v1/projects/${projectId}/generation-reports`))
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to generate the report.') }
  }

  async function openReport(reportId: string) {
    if (!projectId) return
    try {
      setReport(await apiRequest<GenerationReport>(`/v1/projects/${projectId}/generation-reports/${reportId}`))
      setError('')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load the saved report.') }
  }

  async function downloadReport(format: 'json' | 'markdown' | 'csv') {
    if (!report) return
    const extension = format === 'markdown' ? 'md' : format
    try {
      await apiDownload(
        `/v1/projects/${projectId}/generation-reports/${report.id}/export?format=${format}`,
        `generation-report-${report.id}.${extension}`,
      )
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to download this report.') }
  }

  return <>
    <PageHeader eyebrow="API UNDERSTANDING" title="API Explorer" description="Import an OpenAPI or Swagger document and inspect normalized operations and deterministic candidate ideas." />
    <Panel title="Project workspace" subtitle="Projects and imported API specifications are stored in the configured database.">
      <div className="flex flex-wrap items-end gap-3 p-4">
        <label className="min-w-56 flex-1 text-xs text-slate-300">Active project<select className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100" value={projectId} onChange={event => { setProjectId(event.target.value); setPersistedSpecId(''); setReport(null) }}><option value="">Choose a project…</option>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>
        <label className="min-w-48 flex-1 text-xs text-slate-300">New project<input className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100" value={projectName} onChange={event => setProjectName(event.target.value)} placeholder="e.g. Payments API" /></label>
        <Button variant="secondary" onClick={() => void createProject()} disabled={busy || !projectName.trim()}><FolderPlus size={15} />Create project</Button>
      </div>
      {projectId && <div className="border-t border-slate-800 px-4 py-3"><div className="mb-2 flex items-center gap-2 text-xs text-slate-300"><Database size={14} />Saved specifications</div>{savedSpecs.length ? <div className="flex flex-wrap gap-2">{savedSpecs.map(spec => <Button key={spec.id} variant="secondary" onClick={() => void openSavedSpecification(spec.id)}>{spec.title} · {spec.operation_count} operations</Button>)}</div> : <p className="m-0 text-xs text-slate-500">No specifications saved in this project yet.</p>}{savedReports.length > 0 && <><div className="mb-2 mt-4 text-xs text-slate-300">Saved generation reports</div><div className="flex flex-wrap gap-2">{savedReports.map(item => <Button key={item.id} variant="secondary" onClick={() => void openReport(item.id)}>{item.candidate_count} candidates · {new Date(item.created_at).toLocaleString()}</Button>)}</div></>}</div>}
    </Panel>
    <Panel title="Import API specification" subtitle="Accepts OpenAPI 3.0/3.1 JSON or YAML and Swagger 2.0 JSON or YAML. Processing runs through the configured IntelAPI backend.">
      <div className="p-4">
        <div className="mb-2 flex items-center gap-3"><label className="text-xs text-slate-300" htmlFor="openapi-content">Specification content</label><select aria-label="Specification format" className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200" value={sourceFormat} onChange={event => setSourceFormat(event.target.value as 'json' | 'yaml')}><option value="json">JSON</option><option value="yaml">YAML</option></select></div>
        <textarea id="openapi-content" className="min-h-44 w-full rounded-lg border border-slate-700 bg-slate-950 p-3 font-mono text-xs text-slate-200" value={source} onChange={event => setSource(event.target.value)} placeholder="Paste an OpenAPI or Swagger document here…" />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button variant="primary" onClick={() => void parse()} disabled={busy || !source.trim()}><UploadCloud size={15} />{busy ? 'Parsing…' : 'Parse specification'}</Button>
          <label className="cursor-pointer text-xs text-indigo-300 hover:text-indigo-200">Choose spec file<input className="sr-only" type="file" accept="application/json,.json,application/yaml,text/yaml,.yaml,.yml" onChange={event => { const file = event.target.files?.[0]; if (file) { const format = /\.ya?ml$/i.test(file.name) ? 'yaml' : 'json'; void file.text().then(text => { setSource(text); setSourceFormat(format); void parse(text, format) }) } }} /></label>
          {parsed && <Badge tone="info">{parsed.specification.version}</Badge>}
        </div>
        {error && <p role="alert" className="mt-3 text-xs text-rose-300">{error}</p>}
      </div>
    </Panel>
    {parsed ? <>
      <div className="explorer-summary mt-4"><div className="explorer-summary__icon"><FileSearch2 size={21} /></div><div><strong>{parsed.specification.title}</strong><p>Parsed from supplied document · {parsed.specification.version}</p></div><div className="explorer-summary__stats"><span><strong>{parsed.operations.length}</strong> operations</span><Badge tone="info">Current session</Badge></div></div>
      <div className="my-3 flex flex-wrap items-center justify-between gap-3"><div className="flex gap-2"><Button variant="secondary" onClick={() => void saveSpecification()} disabled={saving || !projectId}><Database size={15} />{saving ? 'Saving…' : 'Save to project'}</Button><Button variant="primary" disabled={!persistedSpecId || parsed.operations.length === 0 || parsed.operations.length > 100} onClick={() => void generateReport()}><FileSearch2 size={15} />Generate report</Button></div>{saveMessage && <span role="status" className="text-xs text-emerald-300">{saveMessage}</span>}</div>
      <Panel title="Operations" subtitle="Parsed from the imported document; save it to the selected project to keep it available across sessions." action={<div className="search-field"><Search size={15} /><input value={filter} onChange={event => setFilter(event.target.value)} placeholder="Filter operations…" aria-label="Filter operations" /></div>}>
        <div className="table-wrap"><table><thead><tr><th>METHOD</th><th>PATH</th><th>SUMMARY</th><th>TAGS</th><th /></tr></thead><tbody>{visible.map(operation => <tr key={operation.id}><td><MethodBadge method={operation.method} /></td><td><code className="path-code">{operation.path}</code></td><td>{operation.summary || operation.description}</td><td className="muted-cell">{operation.tags.join(', ')}</td><td><Button variant="secondary" onClick={() => void preview(operation)}>Preview tests</Button></td></tr>)}</tbody></table>{visible.length === 0 && <div className="table-empty">No operations match this filter.</div>}</div>
      </Panel>
      {report && <Panel title={`Generation report · ${report.policy_version}`} subtitle={`${report.summary.candidate_count} persisted candidates across ${report.summary.endpoints_with_candidates} of ${report.summary.operation_count} endpoints. Created ${new Date(report.created_at).toLocaleString()}.`} action={<div className="flex gap-2">{(['json', 'markdown', 'csv'] as const).map(format => <Button key={format} size="sm" onClick={() => void downloadReport(format)}><Download size={13} />{format.toUpperCase()}</Button>)}</div>}>
        {report.summary.truncated && <p role="status" className="px-4 pt-3 text-xs text-amber-300">Report reached its configured cap. Import fewer operations to preview the remainder.</p>}
        <div className="divide-y divide-slate-800">{report.endpoints.map(endpoint => <div key={endpoint.operation.id} className="p-4"><div className="mb-2 flex flex-wrap items-center gap-2"><MethodBadge method={endpoint.operation.method} /><code className="path-code">{endpoint.operation.path}</code><Badge tone="info">{endpoint.candidate_count} candidates</Badge></div>{endpoint.candidates.map(candidate => <div key={candidate.id} className="ml-3 border-l border-slate-700 py-2 pl-3"><p className="m-0 text-xs text-slate-200">{candidate.reason}</p><code className="mt-1 block break-all text-[11px] text-slate-500">{JSON.stringify(candidate.mutation)}</code></div>)}{endpoint.candidate_count === 0 && <p className="m-0 text-xs text-slate-500">No supported candidates from the declared schema.</p>}</div>)}</div>
      </Panel>}
      {selected && <Panel title={`Candidate preview · ${selected.method} ${selected.path}`} subtitle="Deterministic suggestions derived from declared parameters and request-body constraints.">
        {candidates.length ? <div className="divide-y divide-slate-800">{candidates.map(candidate => <div key={candidate.id} className="flex flex-col gap-2 p-4 sm:flex-row sm:items-start"><Badge tone="info">{candidate.kind}</Badge><div className="min-w-0 flex-1"><p className="m-0 text-xs text-slate-200">{candidate.reason}</p><code className="mt-1 block break-all text-[11px] text-slate-400">{JSON.stringify(candidate.mutation)}</code></div><span className="text-[10px] text-slate-500">{candidate.validation_status}</span></div>)}</div> : <div className="p-5 text-xs text-slate-400">No supported schema boundary candidates were found for this operation.</div>}
      </Panel>}
    </> : <div className="mt-4"><Panel title="No specification loaded" subtitle="Paste or select an OpenAPI JSON document to view its actual operations."><div className="p-5 text-xs text-slate-400">No document has been parsed in this session.</div></Panel></div>}
  </>
}
