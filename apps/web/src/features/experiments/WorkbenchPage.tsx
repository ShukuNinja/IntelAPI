import { useCallback, useEffect, useMemo, useState } from 'react'
import { Download, FlaskConical, Play, RefreshCw, Sparkles } from 'lucide-react'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { apiDownload, apiRequest } from '../../lib/apiClient'
import { useProjectWorkspace } from '../projects/ProjectWorkspaceContext'

type Spec = { id: string; title: string; version: string; operation_count: number; servers: string[] }
type WorkbenchOperation = { id: string; operation_id?: string; method: string; path: string; summary?: string; parameters?: { name: string; in: string; required?: boolean }[]; request_body?: { required?: boolean } }
type Run = { id: string; approach: 'contract_baseline' | 'semantic_guided'; status: string; created_at: string; configuration: Record<string, unknown>; result: { metrics: Record<string, number | null>; facts: Fact[]; selected_candidates: Candidate[]; generated_candidates: Candidate[]; execution_results: { candidate_id: string; outcome: string; status_code: number | null; assertions: { kind: string; passed: boolean | null }[] }[]; ground_truth: { available: boolean; reason?: string } } }
type Candidate = { id: string; operation_id: string; operation: { method: string; path: string; summary?: string }; kind: string; reason: string; score: number | null; score_breakdown: Record<string, number> | null }
type Fact = { fact_type: string; value: unknown; source_operation: string; source_location: string; rule: string; evidence_strength: number; evidence: string }
type ExperimentSummary = { id: string; approach: Run['approach']; status: string; created_at: string; metrics: Run['result']['metrics'] }
const benchmarkSpec = {
  openapi: '3.1.0',
  info: { title: 'IntelAPI Seeded Defect Benchmark', version: '1.0.0', description: 'Deterministic localhost fixture. Defect B-001 is deliberately seeded at widget_id 13.' },
  'x-intelapi-benchmark': { id: 'intelapi-seeded-v1', defects: [{ id: 'B-001', operationId: 'getWidget', parameter: 'widget_id', value: 13, expected: 'response property id is integer', actual: 'response property id is string' }] },
  paths: { '/widgets/{widget_id}': { get: { operationId: 'getWidget', summary: 'Retrieve a widget', parameters: [{ name: 'widget_id', in: 'path', required: true, schema: { type: 'integer', minimum: 1, maximum: 1000 } }], responses: { '200': { description: 'Widget', content: { 'application/json': { schema: { type: 'object', required: ['id', 'name'], properties: { id: { type: 'integer', minimum: 1 }, name: { type: 'string', minLength: 1 } } } } }, '404': { description: 'Widget not found' } } } } } },
}
const metricLabels: Record<string, string> = { generation_duration_ms: 'Generation duration (ms)', semantic_extraction_duration_ms: 'Semantic extraction (ms)', total_candidates_generated: 'Candidates generated', unique_candidates: 'Unique candidates', candidates_selected: 'Selected for execution', candidate_selection_rate: 'Selection rate', operations_covered: 'Operations covered', operation_coverage_percent: 'Operation coverage (%)', constraints_covered: 'Constraints covered', constraint_count: 'Measurable constraints', constraint_coverage_percent: 'Constraint coverage (%)', executions_completed: 'Executions completed', assertion_passes: 'Assertion passes', assertion_failures: 'Assertion failures', inconclusive_outcomes: 'Inconclusive outcomes', execution_duration_ms: 'Execution duration (ms)', known_seeded_defects_detected: 'Seeded defects detected', precision: 'Precision', recall: 'Recall', f1: 'F1 score', detection_rate: 'Detection rate', time_to_first_seeded_defect_ms: 'Time to first seeded defect (ms)' }

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
  const [baselines, setBaselines] = useState('{}')
  const [confirmUnsafe, setConfirmUnsafe] = useState(false)
  const [history, setHistory] = useState<ExperimentSummary[]>([])
  const [baselineRun, setBaselineRun] = useState<Run | null>(null)
  const [semanticRun, setSemanticRun] = useState<Run | null>(null)
  const [factsOpen, setFactsOpen] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const root = projectId && specId ? `/v1/projects/${projectId}/specifications/${specId}/experiments` : ''

  useEffect(() => {
    if (!projectId) { setSpecs([]); setSpecId(''); setSpecOperations([]); setTarget(''); setBaselines('{}'); return }
    let current = true
    setSpecs([]); setSpecId(''); setSpecOperations([]); setTarget(''); setBaselines('{}')
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
    void apiRequest<{ operations: WorkbenchOperation[]; servers?: string[]; document: { servers?: { url?: string }[] } }>(`/v1/projects/${projectId}/specifications/${specId}`).then(detail => {
      if (!current) return
      setSpecOperations(detail.operations ?? [])
      const server = detail.servers?.[0] ?? detail.document?.servers?.find(item => item.url)?.url ?? ''
      const isSeeded = detail.operations?.some(operation => operation.operation_id === 'getWidget')
      const hasSeedMarker = (detail.document as { 'x-intelapi-benchmark'?: { id?: string } })?.['x-intelapi-benchmark']?.id === 'intelapi-seeded-v1'
      setTarget(server || (hasSeedMarker ? 'http://localhost:8000/api/v1/research-benchmark' : ''))
      const baselines = Object.fromEntries((detail.operations ?? []).map(operation => [operation.id, {}]))
      const widget = detail.operations?.find(operation => operation.operation_id === 'getWidget')
      if (isSeeded && widget) baselines[widget.id] = { path_parameters: { widget_id: '13' } }
      setBaselines(JSON.stringify(baselines, null, 2))
    }).catch(cause => { if (current) setError(cause instanceof Error ? cause.message : 'Unable to load specification details.') })
    return () => { current = false }
  }, [projectId, specId])
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
      const initialBaselines = Object.fromEntries(imported.operations.map(operation => [operation.id, {}]))
      const getWidget = imported.operations.find(operation => operation.operation_id === 'getWidget')
      if (getWidget) initialBaselines[getWidget.id] = { path_parameters: { widget_id: '13' } }
      setBaselines(JSON.stringify(initialBaselines, null, 2))
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to import specification.') } finally { setBusy(false) }
  }

  function changeProject(nextProjectId: string) {
    setActiveProjectId(nextProjectId)
    setSpecId('')
    setSpecs([])
    setSpecOperations([])
    setBaselineRun(null); setSemanticRun(null); setHistory([])
    setBaselines('{}'); setTarget('')
    setError(''); setNotice('')
  }

  function loadSeededBenchmark() {
    setSource(JSON.stringify(benchmarkSpec, null, 2))
    setFormat('json')
    setTarget('http://localhost:8000/api/v1/research-benchmark')
  }

  async function generate(approach: Run['approach']) {
    if (!root) return
    setBusy(true); setError(''); setNotice('')
    try {
      const run = await apiRequest<Run>(root, { method: 'POST', body: JSON.stringify({ approach, candidate_budget: budget }) })
      if (approach === 'contract_baseline') setBaselineRun(run); else setSemanticRun(run)
      setNotice(`${approach === 'contract_baseline' ? 'Approach A' : 'Approach B'} generation saved as ${run.id}.`)
      await loadHistory()
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Experiment generation failed.') } finally { setBusy(false) }
  }

  async function execute(run: Run) {
    if (!root) return
    if (!target.trim()) { setError('Enter the real API base URL from the imported specification before execution.'); return }
    let parsed: Record<string, unknown>
    try { parsed = JSON.parse(baselines) as Record<string, unknown> } catch { setError('Baseline configuration must be valid JSON.'); return }
    setBusy(true); setError(''); setNotice('')
    try {
      const updated = await apiRequest<Run>(`${root}/${run.id}/execute`, { method: 'POST', body: JSON.stringify({ base_url: target, baselines: parsed, confirm_unsafe: confirmUnsafe, execution_budget: executionBudget }) })
      if (run.approach === 'contract_baseline') setBaselineRun(updated); else setSemanticRun(updated)
      setNotice(`Execution results persisted for ${updated.id}.`); await loadHistory()
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Experiment execution failed.') } finally { setBusy(false) }
  }

  async function retrieve(summary: ExperimentSummary) {
    if (!root) return
    try { const run = await apiRequest<Run>(`${root}/${summary.id}`); if (run.approach === 'contract_baseline') setBaselineRun(run); else setSemanticRun(run) } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to retrieve experiment.') }
  }
  async function exportComparison(format: 'json' | 'markdown') {
    if (!root || !baselineRun || !semanticRun) return
    await apiDownload(`${root}/comparison/export?baseline_run_id=${baselineRun.id}&semantic_run_id=${semanticRun.id}&format=${format}`, `intelapi-comparison.${format === 'markdown' ? 'md' : 'json'}`)
  }

  const runCards = [{ label: 'Approach A · Contract baseline', run: baselineRun, type: 'contract_baseline' as const }, { label: 'Approach B · Semantic guided', run: semanticRun, type: 'semantic_guided' as const }]
  return <>
    <PageHeader eyebrow="RESEARCH EXPERIMENT" title="Experimental Workbench" description="Compare deterministic contract-driven candidate selection with provenance-aware semantic ranking. Generation and target execution are timed and reported separately." />
    {error && <p role="alert" className="mb-3 rounded border border-rose-900 bg-rose-950/40 p-3 text-sm text-rose-200">{error}</p>}
    {notice && <p role="status" className="mb-3 rounded border border-emerald-900 bg-emerald-950/30 p-3 text-sm text-emerald-200">{notice}</p>}
    <Panel title="Experiment inputs" subtitle="Both approaches use the selected persisted specification and candidate foundation.">
      <div className="grid gap-3 p-4 md:grid-cols-2">
        <label className="text-xs text-slate-300">Project<select className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 p-2" value={projectId} onChange={event => changeProject(event.target.value)}><option value="">Select a project…</option>{projects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="text-xs text-slate-300">Imported specification<select className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 p-2" value={specId} onChange={event => { setBaselineRun(null); setSemanticRun(null); setBaselines('{}'); setSpecId(event.target.value) }} disabled={!projectId}><option value="">{projectId ? 'Select a specification…' : 'Select a project first'}</option>{specs.map(item => <option key={item.id} value={item.id}>{item.title} {item.version} · {item.operation_count} operations</option>)}</select></label>
        {!projectId && <p className="m-0 text-xs text-amber-200 md:col-span-2">Choose a project from the app-wide project selector, or click the folder-plus button in the header to create one.</p>}
        {projectId && specs.length === 0 && <p className="m-0 text-xs text-slate-400 md:col-span-2">This project has no imported API specifications yet. Paste a contract below and import it to start an experiment.</p>}
        <div className="md:col-span-2 rounded border border-slate-800 p-3"><p className="m-0 mb-2 text-xs font-semibold text-slate-200">Import OpenAPI / Swagger</p><div className="workbench-import-controls"><select className="rounded border border-slate-700 bg-slate-900 p-2 text-xs" value={format} onChange={event => setFormat(event.target.value as 'json' | 'yaml')}><option value="json">JSON</option><option value="yaml">YAML</option></select><Button size="sm" disabled={busy || !source.trim() || !projectId} onClick={() => void importSpec()}>Import specification</Button><Button size="sm" disabled={!projectId} onClick={loadSeededBenchmark}>Load local seeded benchmark</Button></div><textarea aria-label="OpenAPI document" className="min-h-32 w-full rounded border border-slate-700 bg-slate-950 p-3 font-mono text-xs" value={source} onChange={event => setSource(event.target.value)} placeholder="Paste an OpenAPI 3.x or Swagger 2.0 document" /></div>
        <label className="text-xs text-slate-300">Candidate selection budget<input aria-label="Candidate selection budget" type="number" min={1} max={100} className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 p-2" value={budget} onChange={event => setBudget(Math.max(1, Math.min(100, Number(event.target.value) || 1)))} /></label>
        <div className="flex items-end gap-2"><Button variant="primary" disabled={busy || !root} onClick={() => void generate('contract_baseline')}><FlaskConical size={15} /> Run Approach A</Button><Button variant="primary" disabled={busy || !root} onClick={() => void generate('semantic_guided')}><Sparkles size={15} /> Run Approach B</Button></div>
      </div>
    </Panel>
    <Panel title="Execute selected candidates" subtitle="Set the same target and per-operation valid baseline inputs for both runs. Localhost is permitted by the development policy; unsafe methods still require confirmation.">
      <div className="grid gap-3 p-4 md:grid-cols-2"><label className="text-xs text-slate-300 md:col-span-2">Target base URL<input aria-label="Target base URL" className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 p-2 font-mono" value={target} onChange={event => setTarget(event.target.value)} placeholder="Use the server URL from the imported OpenAPI document" /></label><label className="text-xs text-slate-300">Execution budget<input aria-label="Execution budget" type="number" min={1} max={20} className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 p-2" value={executionBudget} onChange={event => setExecutionBudget(Math.max(1, Math.min(20, Number(event.target.value) || 1)))} /></label><label className="text-xs text-slate-300 md:col-span-2">Baseline values by operation ID (JSON)<textarea aria-label="Baseline values" className="mt-1 min-h-24 w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs" value={baselines} onChange={event => setBaselines(event.target.value)} /></label><p className="m-0 text-[11px] text-slate-500 md:col-span-2">Each operation key is prefilled when possible. Use the operation ID reference below; values may include <code>path_parameters</code>, <code>query_parameters</code>, <code>headers</code>, <code>body</code>, and optional <code>expected_status_code</code>. Missing inputs are reported as inconclusive.</p>{specOperations.length > 0 && <div className="md:col-span-2 rounded border border-slate-800 bg-slate-950/50 p-3"><p className="mb-2 mt-0 text-xs font-medium text-slate-300">Baseline key reference</p><div className="grid gap-2">{specOperations.map(operation => <div key={operation.id} className="text-[10px] text-slate-400"><code className="text-cyan-300">{operation.id}</code><span className="ml-2">{operation.operation_id || `${operation.method} ${operation.path}`} · {operation.method} {operation.path}</span>{operation.parameters?.filter(parameter => parameter.required).length ? <small className="ml-2 block text-amber-200">Required parameters: {operation.parameters.filter(parameter => parameter.required).map(parameter => `${parameter.in}.${parameter.name}`).join(', ')}</small> : null}{operation.request_body?.required && <small className="ml-2 block text-amber-200">Required JSON request body</small>}</div>)}</div></div>}<label className="flex items-center gap-2 text-xs text-amber-200 md:col-span-2"><input type="checkbox" checked={confirmUnsafe} onChange={event => setConfirmUnsafe(event.target.checked)} /> Confirm state-changing HTTP operations for this explicitly chosen target.</label>{runCards.map(({ label, run }) => <div key={label} className="flex items-center justify-between rounded border border-slate-800 p-3"><span className="text-xs text-slate-300">{label}{run && <small className="block text-slate-500">{run.status} · {run.id.slice(0, 8)}</small>}</span><Button size="sm" disabled={busy || !run || run.status === 'executed' || !target.trim()} onClick={() => run && void execute(run)}><Play size={13} /> Execute</Button></div>)}</div>
    </Panel>
    <Panel title="Comparison metrics" subtitle="Values come from persisted run records. Null means the metric is unavailable, not zero." action={baselineRun && semanticRun && <div className="flex gap-1"><Button size="sm" onClick={() => void exportComparison('json')}><Download size={13} /> JSON</Button><Button size="sm" onClick={() => void exportComparison('markdown')}>Markdown</Button></div>}>
      {!baselineRun && !semanticRun ? <div className="p-4 text-xs text-slate-500">Generate either approach to populate the comparison.</div> : <div className="overflow-x-auto"><table className="w-full min-w-[560px] text-left text-xs"><thead className="text-slate-400"><tr><th className="p-3">Metric · definition is documented in the API result</th><th className="p-3">Approach A</th><th className="p-3">Approach B</th></tr></thead><tbody>{Object.keys(metricLabels).map(key => { const a = baselineRun?.result.metrics[key] ?? null; const b = semanticRun?.result.metrics[key] ?? null; return <tr key={key} className="border-t border-slate-800"><th className="p-3 font-medium text-slate-300">{metricLabels[key]}</th><td className="p-3 tabular-nums">{a == null ? 'Unavailable' : typeof a === 'number' ? Number.isInteger(a) ? a : a.toFixed(3) : a}</td><td className="p-3 tabular-nums">{b == null ? 'Unavailable' : typeof b === 'number' ? Number.isInteger(b) ? b : b.toFixed(3) : b}</td></tr> })}</tbody></table></div>}
      {baselineRun && semanticRun && <div className="grid gap-3 p-4 md:grid-cols-2">{[{label:'Approach A selection profile', run:baselineRun},{label:'Approach B selection profile',run:semanticRun}].map(item => <div key={item.label} className="rounded border border-slate-800 p-3"><p className="mb-2 text-xs text-slate-300">{item.label}</p>{(['operation_coverage_percent','constraint_coverage_percent','candidate_selection_rate'] as const).map(key => { const value=item.run!.result.metrics[key]; return <div key={key} className="mb-2"><div className="mb-1 flex justify-between text-[10px] text-slate-500"><span>{metricLabels[key]}</span><span>{value == null ? 'Unavailable' : `${key === 'candidate_selection_rate' ? (value*100).toFixed(1) : value}%`}</span></div><div className="h-2 overflow-hidden rounded bg-slate-800"><div className="h-full bg-cyan-500" style={{width:value == null ? '0%' : `${Math.max(0,Math.min(100,key === 'candidate_selection_rate' ? value*100 : value))}%`}} /></div></div>})}</div>)}</div>}
    </Panel>
    {semanticRun && <Panel title="Semantic fact inspector" subtitle={`${semanticRun.result.facts.length} facts with extraction rule, source location, and evidence strength.`} action={<Button size="sm" onClick={() => setFactsOpen(open => !open)}>{factsOpen ? 'Hide facts' : 'Inspect facts'}</Button>}>
      {factsOpen && <div className="max-h-96 overflow-auto divide-y divide-slate-800">{semanticRun.result.facts.map((fact,index)=><div key={`${fact.source_operation}-${fact.source_location}-${index}`} className="grid gap-1 p-3 text-xs md:grid-cols-[150px_1fr]"><strong className="text-cyan-300">{fact.fact_type}</strong><div className="text-slate-300"><div>{JSON.stringify(fact.value)}</div><div className="mt-1 text-[10px] text-slate-500">{fact.source_location} · {fact.evidence} · strength {fact.evidence_strength} · rule: {fact.rule}</div></div></div>)}</div>}
    </Panel>}
    {(baselineRun || semanticRun) && <Panel title="Selected candidate rationale" subtitle="Approach B includes a transparent contract, intent, workflow, and field-semantics score breakdown.">
      <div className="grid gap-3 p-3 md:grid-cols-2">{runCards.map(({label,run})=><div key={label}><p className="text-xs font-semibold text-slate-300">{label}</p>{(run?.result.selected_candidates ?? []).map(candidate=><div key={candidate.id} className="mb-2 rounded border border-slate-800 p-3 text-xs"><div className="flex justify-between gap-2"><strong>{candidate.kind}</strong><Badge tone="info">{candidate.operation.method} {candidate.operation.path}</Badge></div><p className="my-2 text-slate-400">{candidate.reason}</p>{candidate.score_breakdown && <p className="m-0 text-[10px] text-cyan-300">Score {candidate.score} · {Object.entries(candidate.score_breakdown).map(([key,value])=>`${key} ${value}`).join(' · ')}</p>}</div>)}</div>)}</div>
    </Panel>}
    {(baselineRun?.result.execution_results.length || semanticRun?.result.execution_results.length) ? <Panel title="Execution outcomes" subtitle="Assertion failures are observations and do not by themselves establish an API defect."><div className="grid gap-3 p-3 md:grid-cols-2">{runCards.map(({label,run})=><div key={label}><p className="text-xs font-semibold text-slate-300">{label}</p>{(run?.result.execution_results ?? []).map((row,index)=><div key={`${row.candidate_id}-${index}`} className="mb-2 rounded border border-slate-800 p-3 text-xs"><div className="flex justify-between"><span>Candidate {row.candidate_id.slice(0,8)}</span><Badge tone={row.outcome==='http_response'?'success':'warning'}>{row.status_code ?? row.outcome}</Badge></div>{row.assertions.map((assertion,assertionIndex)=><p key={assertionIndex} className="mb-0 text-slate-400">{assertion.kind}: {assertion.passed == null ? 'inconclusive' : assertion.passed ? 'passed' : 'failed'}</p>)}</div>)}</div>)}</div></Panel> : null}
    <Panel title="Historical experiments" subtitle="Saved in PostgreSQL; retrieve any run after refreshing this page." action={<Button size="sm" disabled={!root} onClick={() => void loadHistory()}><RefreshCw size={13} /> Refresh history</Button>}>
      {history.length === 0 ? <div className="p-4 text-xs text-slate-500">No experiment runs for this specification.</div> : <div className="divide-y divide-slate-800">{history.map(item=><button key={item.id} type="button" onClick={()=>void retrieve(item)} className="flex w-full flex-wrap items-center gap-3 p-3 text-left text-xs hover:bg-slate-900"><Badge tone={item.approach==='semantic_guided'?'info':'neutral'}>{item.approach==='semantic_guided'?'Approach B':'Approach A'}</Badge><span>{item.status}</span><span>{item.metrics.total_candidates_generated ?? 0} candidates · {item.metrics.candidates_selected ?? 0} selected</span><time className="ml-auto text-slate-500">{new Date(item.created_at).toLocaleString()}</time></button>)}</div>}
      {operations.size > 0 && <p className="m-0 px-4 pb-3 text-[10px] text-slate-600">Candidate operation scope currently includes {operations.size} operation(s).</p>}
    </Panel>
  </>
}
