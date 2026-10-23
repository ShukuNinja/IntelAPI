import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
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
type SavedSpecificationDetail = { id: string; title: string; version: string; source_format: 'json' | 'yaml'; source_url: string | null; document: Record<string, unknown>; operations: Operation[] }
type SavedReport = { id: string; specification_id: string; policy_version: string; candidate_count: number; operation_count: number; created_at: string }
type CandidateExecution = { id: string; candidate_id: string; status_code: number; elapsed_ms: number; response_bytes: number; body: unknown; headers: Record<string, string>; run_report: { id: string; assertions: { expected: number; actual: number; passed: boolean }[]; contract_findings: { kind: string; status_code?: number; actual_content_type?: string; mismatches?: { path: string; rule: string; expected: string }[]; skipped_paths?: string[] }[]; next_action: string } }
type DiscoveryCandidate = { source_url: string; specification: { title: string; version: string }; operation_count: number; operations: Operation[]; source_format: 'json' | 'yaml'; document: Record<string, unknown> }
type DiscoveryResult = { classification: string; attempts: { url: string; status_code: number | null; result: string; error?: string }[]; candidates: DiscoveryCandidate[]; ambiguous?: boolean }
type Readiness = { analysis_version: string; scope: string; summary: { operation_count: number; finding_count: number; high_count: number; medium_count: number; low_count: number; operations_needing_attention: number }; findings: { code: string; severity: string; message: string; evidence: { json_pointer: string }; operation_id?: string }[]; limitations: string[] }

export function ExplorerPage() {
  const [searchParams] = useSearchParams()
  const [source, setSource] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [discoveryUrl, setDiscoveryUrl] = useState('')
  const [discovery, setDiscovery] = useState<DiscoveryResult | null>(null)
  const [sourceFormat, setSourceFormat] = useState<'json' | 'yaml'>('json')
  const [filter, setFilter] = useState('')
  const [parsed, setParsed] = useState<ParsedSpec | null>(null)
  const [selected, setSelected] = useState<Operation | null>(null)
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [candidateBaseUrl, setCandidateBaseUrl] = useState('')
  const [candidateQuery, setCandidateQuery] = useState('{}')
  const [candidatePathParams, setCandidatePathParams] = useState('{}')
  const [candidateHeaders, setCandidateHeaders] = useState('{"Accept":"application/json"}')
  const [candidateBody, setCandidateBody] = useState('')
  const [expectedStatus, setExpectedStatus] = useState('')
  const [candidateExecution, setCandidateExecution] = useState<CandidateExecution | null>(null)
  const [report, setReport] = useState<GenerationReport | null>(null)
  const [persistedSpecId, setPersistedSpecId] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [projectName, setProjectName] = useState('')
  const [savedSpecs, setSavedSpecs] = useState<SavedSpecification[]>([])
  const [savedReports, setSavedReports] = useState<SavedReport[]>([])
  const [readiness, setReadiness] = useState<Readiness | null>(null)
  const [saveMessage, setSaveMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const visible = useMemo(() => parsed?.operations.filter(op => `${op.method} ${op.path} ${op.summary} ${op.tags.join(' ')}`.toLowerCase().includes(filter.toLowerCase())) ?? [], [parsed, filter])

  useEffect(() => {
    void apiRequest<Project[]>('/v1/projects').then(items => {
      setProjects(items)
      const requestedProject = searchParams.get('project')
      setProjectId(items.find(project => project.id === requestedProject)?.id ?? items[0]?.id ?? '')
    }).catch(cause => setError(cause instanceof Error ? cause.message : 'Unable to load projects.'))
  }, [searchParams])

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
        method: 'POST', body: JSON.stringify({ content: source, source_format: sourceFormat, source_url: sourceUrl || null }),
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
      setSourceUrl(saved.source_url ?? '')
      setPersistedSpecId(saved.id)
      setReadiness(null)
      setSelected(null); setReport(null); setCandidates([]); setSaveMessage('Loaded from the selected project.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load saved specification.') }
  }

  async function analyzeSpecificationReadiness() {
    if (!projectId || !persistedSpecId) return
    setError('')
    try {
      setReadiness(await apiRequest<Readiness>(`/v1/projects/${projectId}/specifications/${persistedSpecId}/readiness`))
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to analyze specification readiness.') }
  }

  async function parse(text = source, format = sourceFormat) {
    setBusy(true); setError(''); setCandidates([]); setReport(null); setPersistedSpecId('')
    setSourceUrl('')
    try {
      const result = await apiRequest<ParsedSpec>('/v1/specifications/parse', { method: 'POST', body: JSON.stringify({ content: text, source_format: format }) })
      setParsed(result); setSelected(null)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to parse this specification.') }
    finally { setBusy(false) }
  }

  async function discover() {
    setBusy(true); setError(''); setDiscovery(null); setParsed(null); setReport(null); setPersistedSpecId('')
    try {
      const result = await apiRequest<DiscoveryResult>('/v1/discovery/scan', { method: 'POST', body: JSON.stringify({ url: discoveryUrl.trim() }) })
      setDiscovery(result)
      if (result.candidates.length === 1) selectDiscoveryCandidate(result.candidates[0])
      else if (result.candidates.length === 0) setError('No supported API specification was found. Review the attempts and try a direct OpenAPI or Swagger URL.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to discover a specification.') }
    finally { setBusy(false) }
  }

  function selectDiscoveryCandidate(candidate: DiscoveryCandidate) {
    setSource(JSON.stringify(candidate.document, null, 2))
    setSourceFormat(candidate.source_format)
    setSourceUrl(candidate.source_url)
    setParsed({ specification: candidate.specification, operations: candidate.operations })
    setSelected(null); setCandidates([]); setReport(null); setPersistedSpecId('')
    setSaveMessage('Discovered document loaded. Save it to the selected project to continue.')
    setError('')
  }

  async function preview(operation: Operation) {
    setSelected(operation); setError('')
    setCandidateExecution(null)
    try {
      const result = await apiRequest<{ candidates: Candidate[] }>('/v1/specifications/candidates/preview', { method: 'POST', body: JSON.stringify({ operation }) })
      setCandidates(result.candidates)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to preview candidates.') }
  }

  async function executeCandidate(candidate: Candidate) {
    if (!projectId || !persistedSpecId || !selected) {
      setError('Save this specification to the selected project before running a candidate.')
      return
    }
    const unsafe = !['GET', 'HEAD', 'OPTIONS'].includes(selected.method.toUpperCase())
    if (unsafe && !window.confirm(`This candidate sends a ${selected.method} request that may change data on the target. Continue?`)) return
    setError(''); setCandidateExecution(null)
    try {
      const queryParameters = JSON.parse(candidateQuery)
      const pathParameters = JSON.parse(candidatePathParams)
      const headers = JSON.parse(candidateHeaders)
      if (!headers || Array.isArray(headers) || typeof headers !== 'object' || Object.values(headers).some(value => typeof value !== 'string')) throw new Error('Headers must be a JSON object with string values.')
      const body = candidateBody.trim() ? JSON.parse(candidateBody) : null
      const expectedStatusCode = expectedStatus.trim() ? Number(expectedStatus) : null
      if (expectedStatusCode !== null && (!Number.isInteger(expectedStatusCode) || expectedStatusCode < 100 || expectedStatusCode > 599)) throw new Error('Expected status must be an HTTP status code from 100 to 599.')
      const result = await apiRequest<CandidateExecution>(`/v1/projects/${projectId}/specifications/${persistedSpecId}/operations/${encodeURIComponent(selected.id)}/candidates/${encodeURIComponent(candidate.id)}/execute`, {
        method: 'POST',
        body: JSON.stringify({ base_url: candidateBaseUrl, query_parameters: queryParameters, path_parameters: pathParameters, headers, body, confirm_unsafe: unsafe, expected_status_code: expectedStatusCode }),
      })
      setCandidateExecution(result)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to execute this candidate.') }
  }

  async function downloadExecutionReport(format: 'json' | 'markdown' | 'csv') {
    if (!projectId || !candidateExecution) return
    const extension = format === 'markdown' ? 'md' : format
    try {
      await apiDownload(`/v1/projects/${projectId}/execution-reports/${candidateExecution.run_report.id}/export?format=${format}`, `execution-report-${candidateExecution.run_report.id}.${extension}`)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to download the execution report.') }
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
      {projectId && <div className="border-t border-slate-800 px-4 py-3"><div className="mb-2 flex items-center gap-2 text-xs text-slate-300"><Database size={14} />Saved specifications</div>{savedSpecs.length ? <div className="flex flex-wrap gap-2">{savedSpecs.map(spec => <Button key={spec.id} variant="secondary" onClick={() => void openSavedSpecification(spec.id)}>{spec.title} · {spec.operation_count} operations</Button>)}</div> : <p className="m-0 text-xs text-slate-500">No specifications saved in this project yet.</p>}{persistedSpecId && <div className="mt-3"><Button size="sm" onClick={() => void analyzeSpecificationReadiness()}>Analyze specification readiness</Button></div>}{savedReports.length > 0 && <><div className="mb-2 mt-4 text-xs text-slate-300">Saved generation reports</div><div className="flex flex-wrap gap-2">{savedReports.map(item => <Button key={item.id} variant="secondary" onClick={() => void openReport(item.id)}>{item.candidate_count} candidates · {new Date(item.created_at).toLocaleString()}</Button>)}</div></>}</div>}
    {readiness && <Panel title="Specification readiness" subtitle="Documented completeness checks with JSON Pointer evidence; findings do not establish runtime defects."><div className="p-4"><div className="mb-3 flex flex-wrap gap-2"><Badge>{readiness.summary.operation_count} operations</Badge><Badge tone={readiness.summary.high_count ? 'warning' : 'success'}>{readiness.summary.operations_needing_attention} need attention</Badge><Badge>{readiness.summary.finding_count} notes</Badge></div>{readiness.findings.length ? <div className="divide-y divide-slate-800">{readiness.findings.map((finding, index) => <div key={`${finding.code}-${index}`} className="grid gap-1 py-3 sm:grid-cols-[100px_1fr]"><Badge tone={finding.severity === 'high' ? 'warning' : 'neutral'}>{finding.severity} · {finding.code}</Badge><div><p className="m-0 text-xs text-slate-200">{finding.message}</p><code className="text-[11px] text-slate-500">{finding.evidence.json_pointer}</code></div></div>)}</div> : <p className="text-sm text-emerald-300">No documented completeness gaps were found by this rule set.</p>}<ul className="mt-4 space-y-1 text-[11px] text-slate-500">{readiness.limitations.map(item => <li key={item}>{item}</li>)}</ul></div></Panel>}
    </Panel>
    <Panel title="Import API specification" subtitle="Accepts OpenAPI 3.0/3.1 JSON or YAML and Swagger 2.0 JSON or YAML. Processing runs through the configured IntelAPI backend.">
      <div className="p-4">
        <div className="mb-4 rounded-lg border border-slate-800 bg-slate-950/50 p-3">
          <label className="block text-xs text-slate-300" htmlFor="discovery-url">Discover from an API or docs URL</label>
          <div className="mt-2 flex flex-col gap-2 sm:flex-row"><input id="discovery-url" type="url" className="min-w-0 flex-1 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100" value={discoveryUrl} onChange={event => setDiscoveryUrl(event.target.value)} placeholder="https://api.example.com/docs" /><Button variant="secondary" onClick={() => void discover()} disabled={busy || !discoveryUrl.trim()}><Search size={15} />{busy ? 'Scanning…' : 'Discover'}</Button></div>
          <p className="mb-0 mt-2 text-[11px] text-slate-500">The backend checks a bounded set of standard spec paths and Swagger UI configuration. Private and local-network targets are blocked by default.</p>
          {discovery && <div className="mt-3 space-y-2 border-t border-slate-800 pt-3"><div className="text-xs text-slate-300">{discovery.candidates.length} specification{discovery.candidates.length === 1 ? '' : 's'} found · {discovery.classification.replace('_', ' ')}</div>{discovery.candidates.map((candidate, index) => <button key={`${candidate.source_url}-${index}`} type="button" onClick={() => selectDiscoveryCandidate(candidate)} className="flex w-full flex-col items-start gap-1 rounded border border-slate-700 px-3 py-2 text-left hover:border-indigo-500"><span className="text-xs text-slate-100">{candidate.specification.title} · {candidate.specification.version} · {candidate.operation_count} operations</span><code className="break-all text-[10px] text-slate-500">{candidate.source_url}</code></button>)}<details><summary className="cursor-pointer text-[11px] text-slate-400">Discovery attempts ({discovery.attempts.length})</summary><ul className="mt-2 space-y-1 pl-4 text-[10px] text-slate-500">{discovery.attempts.map((attempt, index) => <li key={`${attempt.url}-${index}`}><code className="break-all">{attempt.url}</code> · {attempt.status_code ?? '—'} · {attempt.result}{attempt.error ? ` · ${attempt.error}` : ''}</li>)}</ul></details></div>}
        </div>
        <div className="mb-2 flex items-center gap-3"><label className="text-xs text-slate-300" htmlFor="openapi-content">Specification content</label><select aria-label="Specification format" className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200" value={sourceFormat} onChange={event => { setSourceFormat(event.target.value as 'json' | 'yaml'); setParsed(null); setPersistedSpecId(''); setSourceUrl('') }}><option value="json">JSON</option><option value="yaml">YAML</option></select></div>
        <textarea id="openapi-content" className="min-h-44 w-full rounded-lg border border-slate-700 bg-slate-950 p-3 font-mono text-xs text-slate-200" value={source} onChange={event => { setSource(event.target.value); setSourceUrl(''); setParsed(null); setPersistedSpecId(''); setReport(null) }} placeholder="Paste an OpenAPI or Swagger document here…" />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button variant="primary" onClick={() => void parse()} disabled={busy || !source.trim()}><UploadCloud size={15} />{busy ? 'Parsing…' : 'Parse specification'}</Button>
          <label className="cursor-pointer text-xs text-indigo-300 hover:text-indigo-200">Choose spec file<input className="sr-only" type="file" accept="application/json,.json,application/yaml,text/yaml,.yaml,.yml" onChange={event => { const file = event.target.files?.[0]; if (file) { const format = /\.ya?ml$/i.test(file.name) ? 'yaml' : 'json'; void file.text().then(text => { setSource(text); setSourceFormat(format); void parse(text, format) }) } }} /></label>
          {parsed && <Badge tone="info">{parsed.specification.version}</Badge>}
        </div>
        {error && <p role="alert" className="mt-3 text-xs text-rose-300">{error}</p>}
      </div>
    </Panel>
    {parsed ? <>
      <div className="explorer-summary mt-4"><div className="explorer-summary__icon"><FileSearch2 size={21} /></div><div><strong>{parsed.specification.title}</strong><p>{sourceUrl ? `Discovered from ${sourceUrl}` : 'Parsed from supplied document'} · {parsed.specification.version}</p></div><div className="explorer-summary__stats"><span><strong>{parsed.operations.length}</strong> operations</span><Badge tone="info">Current session</Badge></div></div>
      <div className="my-3 flex flex-wrap items-center justify-between gap-3"><div className="flex gap-2"><Button variant="secondary" onClick={() => void saveSpecification()} disabled={saving || !projectId}><Database size={15} />{saving ? 'Saving…' : 'Save to project'}</Button><Button variant="primary" disabled={!persistedSpecId || parsed.operations.length === 0 || parsed.operations.length > 100} onClick={() => void generateReport()}><FileSearch2 size={15} />Generate report</Button></div>{saveMessage && <span role="status" className="text-xs text-emerald-300">{saveMessage}</span>}</div>
      <Panel title="Operations" subtitle="Parsed from the imported document; save it to the selected project to keep it available across sessions." action={<div className="search-field"><Search size={15} /><input value={filter} onChange={event => setFilter(event.target.value)} placeholder="Filter operations…" aria-label="Filter operations" /></div>}>
        <div className="table-wrap"><table><thead><tr><th>METHOD</th><th>PATH</th><th>SUMMARY</th><th>TAGS</th><th /></tr></thead><tbody>{visible.map(operation => <tr key={operation.id}><td><MethodBadge method={operation.method} /></td><td><code className="path-code">{operation.path}</code></td><td>{operation.summary || operation.description}</td><td className="muted-cell">{operation.tags.join(', ')}</td><td><Button variant="secondary" onClick={() => void preview(operation)}>Preview tests</Button></td></tr>)}</tbody></table>{visible.length === 0 && <div className="table-empty">No operations match this filter.</div>}</div>
      </Panel>
      {report && <Panel title={`Generation report · ${report.policy_version}`} subtitle={`${report.summary.candidate_count} persisted candidates across ${report.summary.endpoints_with_candidates} of ${report.summary.operation_count} endpoints. Created ${new Date(report.created_at).toLocaleString()}.`} action={<div className="flex gap-2">{(['json', 'markdown', 'csv'] as const).map(format => <Button key={format} size="sm" onClick={() => void downloadReport(format)}><Download size={13} />{format.toUpperCase()}</Button>)}</div>}>
        {report.summary.truncated && <p role="status" className="px-4 pt-3 text-xs text-amber-300">Report reached its configured cap. Import fewer operations to preview the remainder.</p>}
        <div className="divide-y divide-slate-800">{report.endpoints.map(endpoint => <div key={endpoint.operation.id} className="p-4"><div className="mb-2 flex flex-wrap items-center gap-2"><MethodBadge method={endpoint.operation.method} /><code className="path-code">{endpoint.operation.path}</code><Badge tone="info">{endpoint.candidate_count} candidates</Badge></div>{endpoint.candidates.map(candidate => <div key={candidate.id} className="ml-3 border-l border-slate-700 py-2 pl-3"><p className="m-0 text-xs text-slate-200">{candidate.reason}</p><code className="mt-1 block break-all text-[11px] text-slate-500">{JSON.stringify(candidate.mutation)}</code></div>)}{endpoint.candidate_count === 0 && <p className="m-0 text-xs text-slate-500">No supported candidates from the declared schema.</p>}</div>)}</div>
      </Panel>}
      {selected && <Panel title={`Candidate preview · ${selected.method} ${selected.path}`} subtitle="Deterministic suggestions derived from declared parameters and request-body constraints.">
        <div className="grid gap-3 border-b border-slate-800 p-4 md:grid-cols-2"><label className="text-xs text-slate-300">Target API base URL<input className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-xs text-slate-100" value={candidateBaseUrl} onChange={event => setCandidateBaseUrl(event.target.value)} placeholder="https://api.example.com" /></label><label className="text-xs text-slate-300">Expected status (optional)<input className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-xs text-slate-100" value={expectedStatus} onChange={event => setExpectedStatus(event.target.value)} inputMode="numeric" placeholder="e.g. 200" /></label><label className="text-xs text-slate-300">Baseline query parameters (JSON)<textarea className="mt-1 block min-h-16 w-full rounded border border-slate-700 bg-slate-900 p-2 font-mono text-xs text-slate-100" value={candidateQuery} onChange={event => setCandidateQuery(event.target.value)} /></label><label className="text-xs text-slate-300">Baseline path parameters (JSON)<textarea className="mt-1 block min-h-16 w-full rounded border border-slate-700 bg-slate-900 p-2 font-mono text-xs text-slate-100" value={candidatePathParams} onChange={event => setCandidatePathParams(event.target.value)} /></label><label className="text-xs text-slate-300">Request headers (JSON)<textarea className="mt-1 block min-h-16 w-full rounded border border-slate-700 bg-slate-900 p-2 font-mono text-xs text-slate-100" value={candidateHeaders} onChange={event => setCandidateHeaders(event.target.value)} /></label><label className="text-xs text-slate-300 md:col-span-2">Baseline JSON request body<textarea className="mt-1 block min-h-16 w-full rounded border border-slate-700 bg-slate-900 p-2 font-mono text-xs text-slate-100" value={candidateBody} onChange={event => setCandidateBody(event.target.value)} placeholder="Optional; needed for request body candidates" /></label><p className="m-0 text-[11px] text-slate-500 md:col-span-2">The response is shown for this session only. Execution history records outcome and timing, not credentials or response content.</p></div>
        {candidates.length ? <div className="divide-y divide-slate-800">{candidates.map(candidate => <div key={candidate.id} className="flex flex-col gap-2 p-4 sm:flex-row sm:items-start"><Badge tone="info">{candidate.kind}</Badge><div className="min-w-0 flex-1"><p className="m-0 text-xs text-slate-200">{candidate.reason}</p><code className="mt-1 block break-all text-[11px] text-slate-400">{JSON.stringify(candidate.mutation)}</code></div><span className="text-[10px] text-slate-500">{candidate.validation_status}</span><Button size="sm" variant="primary" disabled={!persistedSpecId || !candidateBaseUrl.trim()} onClick={() => void executeCandidate(candidate)}>Run candidate</Button></div>)}</div> : <div className="p-5 text-xs text-slate-400">No supported schema boundary candidates were found for this operation.</div>}
        {!persistedSpecId && <p className="m-0 px-4 pb-4 text-xs text-amber-300">Save the specification to a project to run candidates and record execution metadata.</p>}
        {candidateExecution && <div className="border-t border-slate-800 p-4"><div className="mb-2 flex flex-wrap items-center gap-2"><Badge tone={candidateExecution.status_code < 400 ? 'success' : 'warning'}>{candidateExecution.status_code}</Badge><span className="text-xs text-slate-400">{candidateExecution.elapsed_ms} ms · {candidateExecution.response_bytes} bytes</span>{(['json', 'markdown', 'csv'] as const).map(format => <Button key={format} size="sm" onClick={() => void downloadExecutionReport(format)}>{format.toUpperCase()} report</Button>)}</div>{candidateExecution.run_report.assertions.map((assertion, index) => <p key={index} className="text-xs text-slate-300">Status assertion: expected {assertion.expected}, observed {assertion.actual} · {assertion.passed ? 'passed' : 'failed'}</p>)}{candidateExecution.run_report.contract_findings.map(finding => <div key={finding.kind} className="text-xs text-amber-300"><p>Contract observation: {finding.kind}{finding.status_code ? ` (${finding.status_code})` : finding.actual_content_type ? ` (${finding.actual_content_type})` : ''}; this is not marked as a confirmed defect.</p>{finding.mismatches?.map((item, index) => <p key={index} className="ml-3 text-slate-400">{item.path}: {item.rule} expected {item.expected}</p>)}{finding.skipped_paths?.map(path => <p key={path} className="ml-3 text-slate-400">Schema check skipped at {path}.</p>)}</div>)}<p className="text-xs text-slate-400">{candidateExecution.run_report.next_action}</p><pre className="max-h-80 overflow-auto rounded bg-slate-950 p-3 text-xs text-slate-300">{typeof candidateExecution.body === 'string' ? candidateExecution.body : JSON.stringify(candidateExecution.body, null, 2)}</pre></div>}
      </Panel>}
    </> : <div className="mt-4"><Panel title="No specification loaded" subtitle="Paste or select an OpenAPI JSON document to view its actual operations."><div className="p-5 text-xs text-slate-400">No document has been parsed in this session.</div></Panel></div>}
  </>
}
