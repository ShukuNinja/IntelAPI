import { useCallback, useEffect, useMemo, useState } from 'react'
import { Download, FlaskConical, Play, RefreshCw, Sparkles } from 'lucide-react'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { apiDownload, apiRequest } from '../../lib/apiClient'
import { useProjectWorkspace } from '../projects/ProjectWorkspaceContext'

type Spec = { id: string; title: string; version: string; operation_count: number; servers: string[] }
type Schema = { type?: string; format?: string; enum?: unknown[]; default?: unknown; example?: unknown; minimum?: number; maximum?: number; minLength?: number; maxLength?: number; minItems?: number; required?: string[]; properties?: Record<string, Schema>; items?: Schema; nullable?: boolean }
type WorkbenchParameter = { name: string; in: string; required?: boolean; schema?: Schema; example?: unknown }
type WorkbenchOperation = { id: string; operation_id?: string; method: string; path: string; summary?: string; parameters?: WorkbenchParameter[]; request_body?: { required?: boolean; content?: Record<string, { schema?: Schema; example?: unknown; examples?: Record<string, { value?: unknown }> }> } }
type Run = { id: string; approach: 'contract_baseline' | 'semantic_guided'; status: string; created_at: string; configuration: Record<string, unknown>; result: { metrics: Record<string, number | null>; facts: Fact[]; selected_candidates: Candidate[]; generated_candidates: Candidate[]; execution_results: { candidate_id: string; outcome: string; status_code: number | null; assertions: { kind: string; passed: boolean | null }[] }[]; ground_truth: { available: boolean; reason?: string } } }
type Candidate = { id: string; operation_id: string; operation: { method: string; path: string; summary?: string }; kind: string; reason: string; score: number | null; score_breakdown: Record<string, number> | null }
type Fact = { fact_type: string; value: unknown; source_operation: string; source_location: string; rule: string; evidence_strength: number; evidence: string }
type ExperimentSummary = { id: string; approach: Run['approach']; status: string; created_at: string; metrics: Run['result']['metrics'] }
type SsrfDemoResult = { protection_active: boolean; local_targets_allowed: boolean; private_network_targets_allowed: boolean; network_requests_sent: number; cases: { name: string; target_url: string; protected_decision: string; protected_reason: string; without_protection_simulation: string; network_request_sent: boolean }[] }
const benchmarkSpec = {
  openapi: '3.1.0',
  info: { title: 'IntelAPI Seeded Defect Benchmark', version: '1.0.0', description: 'Deterministic localhost fixture. Defect B-001 is deliberately seeded at widget_id 13.' },
  'x-intelapi-benchmark': { id: 'intelapi-seeded-v1', defects: [{ id: 'B-001', operationId: 'getWidget', parameter: 'widget_id', value: 13, expected: 'response property id is integer', actual: 'response property id is string' }] },
  paths: { '/widgets/{widget_id}': { get: { operationId: 'getWidget', summary: 'Retrieve a widget', parameters: [{ name: 'widget_id', in: 'path', required: true, schema: { type: 'integer', minimum: 1, maximum: 1000 } }], responses: { '200': { description: 'Widget', content: { 'application/json': { schema: { type: 'object', required: ['id', 'name'], properties: { id: { type: 'integer', minimum: 1 }, name: { type: 'string', minLength: 1 } } } } }, '404': { description: 'Widget not found' } } } } } },
}
const metricLabels: Record<string, string> = { generation_duration_ms: 'Generation duration (ms)', semantic_extraction_duration_ms: 'Semantic extraction (ms)', total_candidates_generated: 'Candidates generated', unique_candidates: 'Unique candidates', candidates_selected: 'Selected for execution', candidate_selection_rate: 'Selection rate', operations_covered: 'Operations covered', operation_coverage_percent: 'Operation coverage (%)', constraints_covered: 'Constraints covered', constraint_count: 'Measurable constraints', constraint_coverage_percent: 'Constraint coverage (%)', executions_completed: 'Executions completed', assertion_passes: 'Assertion passes', assertion_failures: 'Assertion failures', inconclusive_outcomes: 'Inconclusive outcomes', execution_duration_ms: 'Execution duration (ms)' }

function schemaValue(schema: Schema | undefined, fieldName = 'value', depth = 0): unknown {
  if (!schema || depth > 8) return 'demo'
  if (schema.default !== undefined) return schema.default
  if (schema.example !== undefined) return schema.example
  if (schema.enum?.length) return schema.enum[0]
  const type = schema.type ?? (schema.properties ? 'object' : undefined)
  if (type === 'object') {
    const required = new Set(schema.required ?? [])
    const properties = schema.properties ?? {}
    const result: Record<string, unknown> = {}
    for (const [name, child] of Object.entries(properties)) {
      if (required.has(name)) result[name] = schemaValue(child, name, depth + 1)
    }
    return result
  }
  if (type === 'array') {
    if (fieldName.toLowerCase().includes('tag')) return ['tag1', 'tag2']
    const count = Math.min(Math.max(schema.minItems ?? 1, 1), 20)
    return Array.from({ length: count }, () => schemaValue(schema.items, fieldName, depth + 1))
  }
  if (type === 'integer' || type === 'number') {
    const lower = schema.minimum ?? 1
    const upper = schema.maximum ?? Math.max(1, lower)
    const value = Math.min(Math.max(lower, type === 'integer' ? Math.ceil(lower) : lower), upper)
    return type === 'integer' ? Math.trunc(value) : value
  }
  if (type === 'boolean') return false
  if (type === 'string' || !type) {
    if (schema.nullable) return 'demo'
    if (schema.format === 'email') return 'demo@example.com'
    if (schema.format === 'date') return '2025-01-01'
    if (schema.format === 'date-time') return '2025-01-01T00:00:00Z'
    const minimumLength = Math.max(1, schema.minLength ?? 1)
    const value = fieldName.toLowerCase().includes('user') ? 'demo' : 'test'
    return value.padEnd(minimumLength, 'x').slice(0, Math.max(minimumLength, schema.maxLength ?? minimumLength))
  }
  return null
}

function buildBaselines(operations: WorkbenchOperation[]): Record<string, Record<string, unknown>> {
  return Object.fromEntries(operations.map(operation => {
    const baseline: Record<string, unknown> = {}
    const pathParameters: Record<string, string> = {}
    const queryParameters: Record<string, unknown> = {}
    const headers: Record<string, string> = {}
    for (const parameter of operation.parameters ?? []) {
      if (!parameter.required) continue
      const value = operation.operation_id === 'getWidget' && parameter.name === 'widget_id'
        ? '13'
        : parameter.example ?? schemaValue(parameter.schema, parameter.name)
      if (parameter.in === 'path') pathParameters[parameter.name] = String(value)
      else if (parameter.in === 'query') queryParameters[parameter.name] = value
      else if (parameter.in === 'header') headers[parameter.name] = String(value)
    }
    if (Object.keys(pathParameters).length) baseline.path_parameters = pathParameters
    if (Object.keys(queryParameters).length) baseline.query_parameters = queryParameters
    if (Object.keys(headers).length) baseline.headers = headers

    const requestBody = operation.request_body
    if (requestBody?.required) {
      const jsonContent = requestBody.content?.['application/json']
      const sample = jsonContent?.example ?? Object.values(jsonContent?.examples ?? {})[0]?.value
      if (sample !== undefined) baseline.body = sample
      else if (jsonContent?.schema) baseline.body = schemaValue(jsonContent.schema, 'body')
    }
    return [operation.id, baseline]
  }))
}

export function WorkbenchPage() {
  const { projects, activeProjectId: projectId, setActiveProjectId } = useProjectWorkspace()
  const [specs, setSpecs] = useState<Spec[]>([])
  const [specId, setSpecId] = useState('')
  const [format, setFormat] = useState<'json' | 'yaml'>('json')
  const [source, setSource] = useState('')
  const [budget, setBudget] = useState(25)
  const [executionBudget, setExecutionBudget] = useState(10)
  const [target, setTarget] = useState('')
  const [specOperations, setSpecOperations] = useState<WorkbenchOperation[]>([])
  const [selectedApproaches, setSelectedApproaches] = useState({ contract_baseline: true, semantic_guided: true })
  const [confirmUnsafe, setConfirmUnsafe] = useState(false)
  const [history, setHistory] = useState<ExperimentSummary[]>([])
  const [baselineRun, setBaselineRun] = useState<Run | null>(null)
  const [semanticRun, setSemanticRun] = useState<Run | null>(null)
  const [factsOpen, setFactsOpen] = useState(false)
  const [ssrfDemo, setSsrfDemo] = useState<SsrfDemoResult | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const root = projectId && specId ? `/v1/projects/${projectId}/specifications/${specId}/experiments` : ''

  useEffect(() => {
    if (!projectId) { setSpecs([]); setSpecId(''); setSpecOperations([]); setTarget(''); return }
    let current = true
    setSpecs([]); setSpecId(''); setSpecOperations([]); setTarget('')
    void apiRequest<Spec[]>(`/v1/projects/${projectId}/specifications`).then(items => {
      if (!current) return
      setSpecs(items)
      setSpecId(items[0]?.id ?? '')
    }).catch(cause => { if (current) setError(cause instanceof Error ? cause.message : 'Unable to load specifications.') })
    return () => { current = false }
  }, [projectId])
  useEffect(() => {
    if (!projectId || !specId) { setSpecOperations([]); return }
    let current = true
    void apiRequest<{ operations: WorkbenchOperation[]; servers?: string[]; source_url?: string | null; document: { servers?: { url?: string }[] } }>(`/v1/projects/${projectId}/specifications/${specId}`).then(detail => {
      if (!current) return
      setSpecOperations(detail.operations ?? [])
      const server = detail.servers?.[0] ?? detail.document?.servers?.find(item => item.url)?.url ?? ''
      const isSeeded = detail.operations?.some(operation => operation.operation_id === 'getWidget')
      const hasSeedMarker = (detail.document as { 'x-intelapi-benchmark'?: { id?: string } })?.['x-intelapi-benchmark']?.id === 'intelapi-seeded-v1'
      let targetUrl = server
      if (server && detail.source_url && !/^https?:\/\//i.test(server)) {
        try { targetUrl = new URL(server, detail.source_url).toString().replace(/\/$/, '') } catch { /* leave an invalid or unsupported server visible for correction */ }
      }
      setTarget(targetUrl || (isSeeded && hasSeedMarker ? 'http://localhost:8000/api/v1/research-benchmark' : ''))
    }).catch(cause => { if (current) setError(cause instanceof Error ? cause.message : 'Unable to load specification details.') })
    return () => { current = false }
  }, [projectId, specId])
  const baselines = useMemo(() => buildBaselines(specOperations), [specOperations])
  const operations = useMemo(() => new Map((baselineRun?.result.selected_candidates ?? semanticRun?.result.selected_candidates ?? []).map(candidate => [candidate.operation_id, candidate.operation])), [baselineRun, semanticRun])

  const loadHistory = useCallback(async () => {
    if (!root) return
    try { setHistory(await apiRequest<ExperimentSummary[]>(root)) } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load experiment history.') }
  }, [root])
  useEffect(() => { setBaselineRun(null); setSemanticRun(null); setHistory([]); void loadHistory() }, [root, loadHistory])

  async function importSpec() {
    if (!projectId || !source.trim()) return
    setBusy(true); setError(''); setNotice('')
    try {
      const imported = await apiRequest<{ id: string; title: string; version: string; servers?: string[]; operations: WorkbenchOperation[] }>('/v1/projects/' + projectId + '/specifications/import', { method: 'POST', body: JSON.stringify({ content: source, source_format: format }) })
      const nextSpecs = await apiRequest<Spec[]>(`/v1/projects/${projectId}/specifications`)
      setSpecs(nextSpecs); setSpecId(imported.id); setNotice(`Imported ${imported.title} ${imported.version}.`); setSource('')
      setSpecOperations(imported.operations)
      const server = imported.servers?.[0] ?? ''
      setTarget(server || (imported.operations.some(operation => operation.operation_id === 'getWidget') ? 'http://localhost:8000/api/v1/research-benchmark' : ''))
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to import specification.') } finally { setBusy(false) }
  }

  function changeProject(nextProjectId: string) {
    setActiveProjectId(nextProjectId)
    setSpecId('')
    setSpecs([])
    setSpecOperations([])
    setBaselineRun(null); setSemanticRun(null); setHistory([])
    setTarget('')
    setError(''); setNotice('')
  }

  function loadSeededBenchmark() {
    setSource(JSON.stringify(benchmarkSpec, null, 2))
    setFormat('json')
    setTarget('http://localhost:8000/api/v1/research-benchmark')
  }

  async function startExperiment() {
    if (!root) return
    if (!target.trim()) { setError('Enter the real API base URL from the imported specification before starting.'); return }
    const approaches = (Object.entries(selectedApproaches) as [Run['approach'], boolean][]).filter(([, selected]) => selected).map(([approach]) => approach)
    if (approaches.length === 0) { setError('Select at least one approach to run.'); return }
    setBusy(true); setError(''); setNotice('')
    setBaselineRun(null); setSemanticRun(null)
    try {
      for (const approach of approaches) {
        const generated = await apiRequest<Run>(root, { method: 'POST', body: JSON.stringify({ approach, candidate_budget: budget }) })
        if (approach === 'contract_baseline') setBaselineRun(generated); else setSemanticRun(generated)
        const completed = await apiRequest<Run>(`${root}/${generated.id}/execute`, {
          method: 'POST',
          body: JSON.stringify({ base_url: target, baselines, confirm_unsafe: confirmUnsafe, execution_budget: executionBudget }),
        })
        if (approach === 'contract_baseline') setBaselineRun(completed); else setSemanticRun(completed)
      }
      setNotice(`Experiment complete. ${approaches.length === 2 ? 'Both approaches' : approaches[0] === 'contract_baseline' ? 'Approach A' : 'Approach B'} generated and executed.`)
      await loadHistory()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Experiment could not be completed.')
    } finally { setBusy(false) }
  }

  async function runSsrfDemo() {
    if (!projectId) return
    setBusy(true); setError(''); setSsrfDemo(null)
    try {
      setSsrfDemo(await apiRequest<SsrfDemoResult>(`/v1/projects/${projectId}/executions/ssrf-demo`))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to run the SSRF policy demonstration.')
    } finally { setBusy(false) }
  }

  async function retrieve(summary: ExperimentSummary) {
    if (!root) return
    try { const run = await apiRequest<Run>(`${root}/${summary.id}`); if (run.approach === 'contract_baseline') setBaselineRun(run); else setSemanticRun(run) } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to retrieve experiment.') }
  }
  async function exportComparison(format: 'json' | 'markdown') {
    if (!root || !baselineRun || !semanticRun) return
    await apiDownload(`${root}/comparison/export?baseline_run_id=${baselineRun.id}&semantic_run_id=${semanticRun.id}&format=${format}`, `intelapi-comparison.${format === 'markdown' ? 'md' : 'json'}`)
  }

  const runCards = [
    ...(selectedApproaches.contract_baseline ? [{ label: 'Approach A · Contract baseline', run: baselineRun, type: 'contract_baseline' as const }] : []),
    ...(selectedApproaches.semantic_guided ? [{ label: 'Approach B · Semantic guided', run: semanticRun, type: 'semantic_guided' as const }] : []),
  ]
  return <>
    <PageHeader eyebrow="RESEARCH EXPERIMENT" title="Experimental Workbench" description="Choose one or both approaches, provide the target, then start a single experiment to generate candidates and execute them." />
    {error && <p role="alert" className="mb-3 rounded border border-rose-900 bg-rose-950/40 p-3 text-sm text-rose-200">{error}</p>}
    {notice && <p role="status" className="mb-3 rounded border border-emerald-900 bg-emerald-950/30 p-3 text-sm text-emerald-200">{notice}</p>}
    <Panel title="Experiment setup" subtitle="The selected approaches use the same API contract and target. Required path, query, header, and JSON body baselines are generated from the contract automatically.">
      <div className="grid gap-3 p-4 md:grid-cols-2">
        <label className="text-xs text-slate-300">Project<select className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 p-2" value={projectId} onChange={event => changeProject(event.target.value)}><option value="">Select a project…</option>{projects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="text-xs text-slate-300">Imported specification<select className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 p-2" value={specId} onChange={event => { setBaselineRun(null); setSemanticRun(null); setSpecId(event.target.value) }} disabled={!projectId}><option value="">{projectId ? 'Select a specification…' : 'Select a project first'}</option>{specs.map(item => <option key={item.id} value={item.id}>{item.title} {item.version} · {item.operation_count} operations</option>)}</select></label>
        {!projectId && <p className="m-0 text-xs text-amber-200 md:col-span-2">Choose a project from the app-wide project selector, or click the folder-plus button in the header to create one.</p>}
        {projectId && specs.length === 0 && <p className="m-0 text-xs text-slate-400 md:col-span-2">This project has no imported API specifications yet. Paste a contract below and import it to start an experiment.</p>}
        <div className="md:col-span-2 rounded border border-slate-800 p-3"><p className="m-0 mb-2 text-xs font-semibold text-slate-200">Import OpenAPI / Swagger</p><div className="workbench-import-controls"><select className="rounded border border-slate-700 bg-slate-900 p-2 text-xs" value={format} onChange={event => setFormat(event.target.value as 'json' | 'yaml')}><option value="json">JSON</option><option value="yaml">YAML</option></select><Button size="sm" disabled={busy || !source.trim() || !projectId} onClick={() => void importSpec()}>Import specification</Button><Button size="sm" disabled={!projectId} onClick={loadSeededBenchmark}>Load local seeded benchmark</Button></div><textarea aria-label="OpenAPI document" className="min-h-32 w-full rounded border border-slate-700 bg-slate-950 p-3 font-mono text-xs" value={source} onChange={event => setSource(event.target.value)} placeholder="Paste an OpenAPI 3.x or Swagger 2.0 document" /></div>
        <label className="text-xs text-slate-300">Target base URL<input aria-label="Target base URL" className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 p-2 font-mono" value={target} onChange={event => setTarget(event.target.value)} placeholder="https://api.example.com/v1" /><small className="mt-1 block text-slate-500">The app derives a target from the specification when possible. Confirm this is the API you intend to call.</small></label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-xs text-slate-300">Candidate selection budget<input aria-label="Candidate selection budget" type="number" min={1} max={100} className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 p-2" value={budget} onChange={event => setBudget(Math.max(1, Math.min(100, Number(event.target.value) || 1)))} /><small className="mt-1 block text-slate-500">How many candidates each approach selects for the experiment.</small></label>
          <label className="text-xs text-slate-300">Execution budget<input aria-label="Execution budget" type="number" min={1} max={20} className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 p-2" value={executionBudget} onChange={event => setExecutionBudget(Math.max(1, Math.min(20, Number(event.target.value) || 1)))} /><small className="mt-1 block text-slate-500">Maximum real API calls per selected approach.</small></label>
        </div>
        <fieldset className="grid gap-2 rounded border border-slate-800 p-3 md:col-span-2">
          <legend className="px-1 text-xs font-semibold text-slate-200">Approaches to run</legend>
          <label className="flex items-start gap-2 text-xs text-slate-300"><input type="checkbox" checked={selectedApproaches.contract_baseline} onChange={event => setSelectedApproaches(current => ({ ...current, contract_baseline: event.target.checked }))} /><span><strong className="flex items-center gap-1"><FlaskConical size={14} /> Approach A · Contract baseline</strong><small className="mt-1 block text-slate-500">Selects candidates using contract rules and constraints.</small></span></label>
          <label className="flex items-start gap-2 text-xs text-slate-300"><input type="checkbox" checked={selectedApproaches.semantic_guided} onChange={event => setSelectedApproaches(current => ({ ...current, semantic_guided: event.target.checked }))} /><span><strong className="flex items-center gap-1"><Sparkles size={14} /> Approach B · Semantic guided</strong><small className="mt-1 block text-slate-500">Ranks candidates using extracted meaning and evidence from the contract.</small></span></label>
        </fieldset>
        <div className="rounded border border-amber-900/70 bg-amber-950/20 p-3 text-xs text-amber-100 md:col-span-2">
          <label className="flex items-start gap-2 font-medium"><input type="checkbox" checked={confirmUnsafe} onChange={event => setConfirmUnsafe(event.target.checked)} /> Allow state-changing HTTP operations for this target.</label>
          <p className="mb-0 mt-2 text-[11px] leading-relaxed text-amber-200/80">When unchecked, requests using methods such as POST, PUT, PATCH, or DELETE are blocked and shown as blocked outcomes. When checked, the selected candidates may create, update, or delete data on the target. If you select both approaches, each approach can make its own calls. Use a disposable test API for state-changing requests.</p>
        </div>
        <p className="m-0 text-[11px] text-slate-500 md:col-span-2">Required baseline values (such as path IDs, query enums, and required JSON fields) are derived from the selected OpenAPI schema. Authentication credentials are never invented; an API that requires credentials may return 401 or 403.</p>
        <div className="md:col-span-2"><Button variant="primary" disabled={busy || !root || !target.trim() || !Object.values(selectedApproaches).some(Boolean)} onClick={() => void startExperiment()}><Play size={15} />{busy ? 'Experiment running…' : 'Start experiment'}</Button></div>
      </div>
    </Panel>
    <Panel title="SSRF protection demo" subtitle="Compare the active destination policy with a simulated vulnerable client using fixed demonstration addresses.">
      <div className="flex flex-wrap items-center justify-between gap-3 p-4">
        <p className="m-0 max-w-3xl text-xs leading-relaxed text-slate-400">This preflight checks loopback, private, link-local metadata, reserved, and public control addresses through the same destination validator used before outbound requests. It sends no HTTP requests and never disables SSRF protection.</p>
        <Button variant="secondary" disabled={busy || !projectId} onClick={() => void runSsrfDemo()}>{busy ? 'Checking policy…' : 'Run safe SSRF demo'}</Button>
      </div>
      {!projectId && <p className="m-0 px-4 pb-4 text-xs text-amber-200">Select a project to run this policy demonstration.</p>}
      {ssrfDemo && <div className="border-t border-slate-800">
        <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-xs"><Badge tone={ssrfDemo.protection_active ? 'success' : 'warning'}>{ssrfDemo.protection_active ? 'SSRF protection active' : 'SSRF protection unavailable'}</Badge><span className="text-slate-400">Loopback targets: {ssrfDemo.local_targets_allowed ? 'allowed by development policy' : 'blocked'} · Private network targets: {ssrfDemo.private_network_targets_allowed ? 'allowed by configuration' : 'blocked'}</span><span className="text-slate-400">Network requests sent: {ssrfDemo.network_requests_sent}</span></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-xs"><thead className="text-slate-400"><tr><th className="p-3">Safe test case</th><th className="p-3">With protection</th><th className="p-3">Without protection · simulated</th></tr></thead><tbody>{ssrfDemo.cases.map(item => <tr key={item.target_url} className="border-t border-slate-800"><td className="p-3"><strong className="block text-slate-200">{item.name}</strong><code className="mt-1 block text-[10px] text-slate-500">{item.target_url}</code></td><td className="p-3"><Badge tone={item.protected_decision === 'blocked_by_policy' ? 'warning' : 'success'}>{item.protected_decision}</Badge><span className="mt-1 block max-w-md text-[10px] leading-relaxed text-slate-400">{item.protected_reason}</span></td><td className="p-3 text-[10px] leading-relaxed text-slate-400">{item.without_protection_simulation}</td></tr>)}</tbody></table></div>
        <p className="m-0 px-4 pb-4 text-[10px] text-slate-500">The “without protection” column describes the risk only. It is not an executable mode. None of these targets are contacted by this demo; this includes loopback even when the development policy allows it.</p>
      </div>}
    </Panel>
    <Panel title="Experiment results" subtitle="Metrics and request outcomes for the selected approach or approaches." action={selectedApproaches.contract_baseline && selectedApproaches.semantic_guided && baselineRun && semanticRun && <div className="flex gap-1"><Button size="sm" onClick={() => void exportComparison('json')}><Download size={13} /> JSON</Button><Button size="sm" onClick={() => void exportComparison('markdown')}>Markdown</Button></div>}>
      {!runCards.some(card => card.run) ? <div className="p-4 text-xs text-slate-500">Choose an approach above and click Start experiment to populate its results.</div> : <div className="overflow-x-auto"><table className="w-full min-w-[420px] text-left text-xs"><thead className="text-slate-400"><tr><th className="p-3">Metric</th>{runCards.map(card => <th key={card.type} className="p-3">{card.type === 'contract_baseline' ? 'Approach A' : 'Approach B'}</th>)}</tr></thead><tbody>{Object.entries(metricLabels).map(([key, label]) => <tr key={key} className="border-t border-slate-800"><th className="p-3 font-medium text-slate-300">{label}</th>{runCards.map(card => { const value = card.run?.result.metrics[key] ?? null; return <td key={card.type} className="p-3 tabular-nums">{value == null ? 'Unavailable' : Number.isInteger(value) ? value : value.toFixed(3)}</td> })}</tr>)}</tbody></table></div>}
      {selectedApproaches.contract_baseline && selectedApproaches.semantic_guided && baselineRun && semanticRun && <div className="grid gap-3 p-4 md:grid-cols-2">{[{label:'Approach A selection profile', run:baselineRun},{label:'Approach B selection profile',run:semanticRun}].map(item => <div key={item.label} className="rounded border border-slate-800 p-3"><p className="mb-2 text-xs text-slate-300">{item.label}</p>{(['operation_coverage_percent','constraint_coverage_percent','candidate_selection_rate'] as const).map(key => { const value=item.run!.result.metrics[key]; return <div key={key} className="mb-2"><div className="mb-1 flex justify-between text-[10px] text-slate-500"><span>{metricLabels[key]}</span><span>{value == null ? 'Unavailable' : `${key === 'candidate_selection_rate' ? (value*100).toFixed(1) : value}%`}</span></div><div className="h-2 overflow-hidden rounded bg-slate-800"><div className="h-full bg-cyan-500" style={{width:value == null ? '0%' : `${Math.max(0,Math.min(100,key === 'candidate_selection_rate' ? value*100 : value))}%`}} /></div></div>})}</div>)}</div>}
    </Panel>
    {selectedApproaches.semantic_guided && semanticRun && <Panel title="Semantic fact inspector" subtitle={`${semanticRun.result.facts.length} facts with extraction rule, source location, and evidence strength.`} action={<Button size="sm" onClick={() => setFactsOpen(open => !open)}>{factsOpen ? 'Hide facts' : 'Inspect facts'}</Button>}>
      {factsOpen && <div className="max-h-96 overflow-auto divide-y divide-slate-800">{semanticRun.result.facts.map((fact,index)=><div key={`${fact.source_operation}-${fact.source_location}-${index}`} className="grid gap-1 p-3 text-xs md:grid-cols-[150px_1fr]"><strong className="text-cyan-300">{fact.fact_type}</strong><div className="text-slate-300"><div>{JSON.stringify(fact.value)}</div><div className="mt-1 text-[10px] text-slate-500">{fact.source_location} · {fact.evidence} · strength {fact.evidence_strength} · rule: {fact.rule}</div></div></div>)}</div>}
    </Panel>}
    {(baselineRun || semanticRun) && <Panel title="Selected candidate rationale" subtitle="Approach B includes a transparent contract, intent, workflow, and field-semantics score breakdown.">
      <div className="grid gap-3 p-3 md:grid-cols-2">{runCards.map(({label,run})=><div key={label}><p className="text-xs font-semibold text-slate-300">{label}</p>{(run?.result.selected_candidates ?? []).map(candidate=><div key={candidate.id} className="mb-2 rounded border border-slate-800 p-3 text-xs"><div className="flex justify-between gap-2"><strong>{candidate.kind}</strong><Badge tone="info">{candidate.operation.method} {candidate.operation.path}</Badge></div><p className="my-2 text-slate-400">{candidate.reason}</p>{candidate.score_breakdown && <p className="m-0 text-[10px] text-cyan-300">Score {candidate.score} · {Object.entries(candidate.score_breakdown).map(([key,value])=>`${key} ${value}`).join(' · ')}</p>}</div>)}</div>)}</div>
    </Panel>}
    {(runCards.some(({ run }) => (run?.result.execution_results.length ?? 0) > 0)) ? <Panel title="Execution outcomes" subtitle="Assertion failures are observations and do not by themselves establish an API defect."><div className="grid gap-3 p-3 md:grid-cols-2">{runCards.map(({label,run})=><div key={label}><p className="text-xs font-semibold text-slate-300">{label}</p>{(run?.result.execution_results ?? []).map((row,index)=><div key={`${row.candidate_id}-${index}`} className="mb-2 rounded border border-slate-800 p-3 text-xs"><div className="flex justify-between"><span>Candidate {row.candidate_id.slice(0,8)}</span><Badge tone={row.outcome==='http_response'?'success':'warning'}>{row.status_code ?? row.outcome}</Badge></div>{row.assertions.map((assertion,assertionIndex)=><p key={assertionIndex} className="mb-0 text-slate-400">{assertion.kind}: {assertion.passed == null ? 'inconclusive' : assertion.passed ? 'passed' : 'failed'}</p>)}</div>)}</div>)}</div></Panel> : null}
    <Panel title="Historical experiments" subtitle="Saved in PostgreSQL; retrieve any run after refreshing this page." action={<Button size="sm" disabled={!root} onClick={() => void loadHistory()}><RefreshCw size={13} /> Refresh history</Button>}>
      {history.length === 0 ? <div className="p-4 text-xs text-slate-500">No experiment runs for this specification.</div> : <div className="divide-y divide-slate-800">{history.map(item=><button key={item.id} type="button" onClick={()=>void retrieve(item)} className="flex w-full flex-wrap items-center gap-3 p-3 text-left text-xs hover:bg-slate-900"><Badge tone={item.approach==='semantic_guided'?'info':'neutral'}>{item.approach==='semantic_guided'?'Approach B':'Approach A'}</Badge><span>{item.status}</span><span>{item.metrics.total_candidates_generated ?? 0} candidates · {item.metrics.candidates_selected ?? 0} selected</span><time className="ml-auto text-slate-500">{new Date(item.created_at).toLocaleString()}</time></button>)}</div>}
      {operations.size > 0 && <p className="m-0 px-4 pb-3 text-[10px] text-slate-600">Candidate operation scope currently includes {operations.size} operation(s).</p>}
    </Panel>
  </>
}
