import { useCallback, useEffect, useMemo, useState } from 'react'
import { BarChart3, Download, RefreshCw, Rocket } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { EmptyState } from '../../components/ui/EmptyState'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { apiRequest } from '../../lib/apiClient'
import { campaignService, type CampaignExecution, type CampaignReport, type CampaignTestCase } from '../campaigns/campaignService'
import { useProject } from '../projects/ProjectContext'
import { specificationService, type ApiOperation, type Specification } from '../explorer/specificationService'
import { experimentService, approachDetails, type Experiment, type ExperimentApproach, type ExperimentComparison, type ExperimentMetric, type LlmProviderOptions } from './experimentService'

interface EnvironmentOption {
  id: string
  name: string
  base_url: string | null
}

interface RunInspection {
  tests: CampaignTestCase[]
  executions: CampaignExecution[]
  report: CampaignReport
}

const approachOrder: ExperimentApproach[] = [
  'llm_baseline',
  'semantic_assisted',
  'feedback_guided',
  'evidence_backed',
]

function metricText(value: ExperimentMetric | undefined): string {
  if (!value) return 'N/A'
  if ('value' in value) {
    if (value.value === null || value.value === undefined) return 'N/A'
    return typeof value.value === 'number' ? value.value.toLocaleString() : value.value
  }
  return Object.entries(value).map(([key, count]) => `${key.replaceAll('_', ' ')}: ${count}`).join(' · ')
}

function metricReason(value: ExperimentMetric | undefined): string | null {
  if (!value || !('unavailable_reason' in value)) return null
  return typeof value.unavailable_reason === 'string' ? value.unavailable_reason : null
}

function tone(state: string): 'success' | 'danger' | 'info' | 'neutral' {
  if (state === 'completed') return 'success'
  if (state === 'completed_with_fallback') return 'info'
  if (state === 'failed' || state === 'generation_failed' || state === 'partial') return 'danger'
  if (state === 'queued' || state === 'running') return 'info'
  return 'neutral'
}

function runSummary(run: Experiment['runs'][number], inspection?: RunInspection): { title: string; detail: string; tone: 'success' | 'danger' | 'info' | 'neutral' } {
  const mode = String(run.generation_metadata.mode ?? '')
  const llmStatus = String(run.generation_metadata.llm_status ?? '')
  if (run.state === 'generation_failed') return { title: 'Generation failed', detail: 'No executable test candidates were available. Review the provider and rejection diagnostics below.', tone: 'danger' }
  if (mode === 'llm') {
    const failed = inspection?.executions.filter(item => item.status === 'failed').length ?? 0
    const completed = inspection?.executions.filter(item => item.status === 'completed').length ?? 0
    return { title: 'LLM candidates used', detail: `${Number(run.generation_metadata.valid_candidate_count ?? run.candidate_count)} candidates passed validation. ${inspection ? `${completed} requests completed and ${failed} failed.` : 'Loading request outcomes…'} Request completion does not alone mean the behavior passed.`, tone: failed ? 'danger' : 'success' }
  }
  if (mode === 'deterministic_fallback') return { title: 'Fallback candidates used', detail: typeof run.generation_metadata.warning === 'string' ? run.generation_metadata.warning : 'The LLM candidates were unavailable; deterministic candidates were used.', tone: 'info' }
  if (llmStatus === 'not_used') return { title: 'LLM not used', detail: 'This approach selects deterministic candidates by design.', tone: 'neutral' }
  if (!inspection) return { title: run.state === 'completed' ? 'Run complete' : 'Run in progress', detail: 'Loading test outcomes…', tone: 'info' }
  const passed = inspection.executions.filter(item => item.status === 'completed').length
  const failed = inspection.executions.filter(item => item.status === 'failed').length
  return { title: failed ? `${failed} request${failed === 1 ? '' : 's'} failed` : `${passed} request${passed === 1 ? '' : 's'} completed`, detail: failed ? 'Inspect the failed test rows below for the response or connection error.' : 'A completed request means the target responded; it does not alone prove the API behavior is correct.', tone: failed ? 'danger' : 'success' }
}

function outcomeMeaning(execution?: CampaignExecution): string {
  if (!execution) return 'This test has not run yet.'
  if (execution.status === 'failed') return 'The request could not complete successfully. Review the error and response details.'
  if (execution.status === 'completed') return 'The API returned a response. Check the expected behavior and response below to judge correctness.'
  return `Execution status: ${execution.status}.`
}

export function ExperimentWorkbenchPage() {
  const { project } = useProject()
  const [specifications, setSpecifications] = useState<Specification[]>([])
  const [specificationId, setSpecificationId] = useState('')
  const [operations, setOperations] = useState<ApiOperation[]>([])
  const [environments, setEnvironments] = useState<EnvironmentOption[]>([])
  const [environmentId, setEnvironmentId] = useState('')
  const [selectedOperations, setSelectedOperations] = useState<string[]>([])
  const [selectedApproaches, setSelectedApproaches] = useState<ExperimentApproach[]>(approachOrder)
  const [useLlm, setUseLlm] = useState(false)
  const [llmProviders, setLlmProviders] = useState<LlmProviderOptions | null>(null)
  const [llmProvider, setLlmProvider] = useState<'nvidia' | 'groq'>('nvidia')
  const [llmModel, setLlmModel] = useState('')
  const [llmCandidateCount, setLlmCandidateCount] = useState(4)
  const [name, setName] = useState('')
  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [selectedExperimentId, setSelectedExperimentId] = useState('')
  const [comparison, setComparison] = useState<ExperimentComparison | null>(null)
  const [inspections, setInspections] = useState<Record<string, RunInspection>>({})
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!project) {
      setSpecifications([]); setOperations([]); setEnvironments([]); setExperiments([])
      setLoading(false)
      return
    }
    try {
      setLoading(true)
      const [specResult, environmentResult, experimentResult, providerResult] = await Promise.all([
        specificationService.list(project.id),
        apiRequest<{ items: EnvironmentOption[] }>(`/v1/projects/${project.id}/environments`),
        experimentService.list(project.id),
        experimentService.providers(),
      ])
      setSpecifications(specResult.items)
      setEnvironments(environmentResult.items.filter(environment => environment.base_url))
      setEnvironmentId(current => environmentResult.items.some(environment => environment.id === current && environment.base_url) ? current : '')
      setExperiments(experimentResult.items)
      setLlmProviders(providerResult)
      setLlmProvider(current => providerResult.providers.some(item => item.id === current) ? current : providerResult.default_provider)
      setLlmModel(current => current || providerResult.providers.find(item => item.id === providerResult.default_provider)?.model || '')
      setSpecificationId(current => specResult.items.some(item => item.id === current) ? current : (specResult.items[0]?.id ?? ''))
      setSelectedExperimentId(current => experimentResult.items.some(item => item.id === current) ? current : (experimentResult.items[0]?.id ?? ''))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load workbench data.')
    } finally {
      setLoading(false)
    }
  }, [project])

  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    if (!specificationId) { setOperations([]); setSelectedOperations([]); return }
    void specificationService.operations(specificationId)
      .then(result => {
        setOperations(result.items)
        setSelectedOperations(current => current.filter(id => result.items.some(operation => operation.id === id)))
      })
      .catch(err => setError(err instanceof Error ? err.message : 'Unable to load operations.'))
  }, [specificationId])
  useEffect(() => {
    if (!selectedExperimentId) { setComparison(null); return }
    void experimentService.compare(selectedExperimentId)
      .then(setComparison)
      .catch(err => setError(err instanceof Error ? err.message : 'Unable to load comparison.'))
  }, [selectedExperimentId, experiments])
  useEffect(() => {
    const runs = comparison?.experiment.runs ?? []
    if (!runs.length) { setInspections({}); return }
    let active = true
    void Promise.all(runs.map(async run => {
      const [tests, report, firstPage] = await Promise.all([
        campaignService.tests(run.campaign_id),
        campaignService.report(run.campaign_id),
        campaignService.executions(run.campaign_id, 100),
      ])
      const pageCount = Math.ceil(Math.max(0, firstPage.total - firstPage.items.length) / firstPage.limit)
      const pages = await Promise.all(Array.from({ length: pageCount }, (_, index) =>
        campaignService.executions(run.campaign_id, firstPage.limit, firstPage.items.length + index * firstPage.limit),
      ))
      return {
        campaignId: run.campaign_id,
        inspection: { tests, report, executions: [...firstPage.items, ...pages.flatMap(page => page.items)] },
      }
    })).then(results => {
      if (active) setInspections(Object.fromEntries(results.map(item => [item.campaignId, item.inspection])))
    }).catch(err => {
      if (active) setError(err instanceof Error ? err.message : 'Unable to load run evidence.')
    })
    return () => { active = false }
  }, [comparison])
  useEffect(() => {
    if (!experiments.some(item => item.state === 'queued' || item.state === 'running')) return
    const timer = window.setInterval(() => void refresh(), 4000)
    return () => window.clearInterval(timer)
  }, [experiments, refresh])

  const selectedSpecification = specifications.find(item => item.id === specificationId)
  const selectedEnvironment = environments.find(item => item.id === environmentId)
  const canCreate = Boolean(project && name.trim() && selectedSpecification && selectedOperations.length && selectedApproaches.length && selectedEnvironment)
  const metrics = useMemo(() => comparison?.metrics_by_approach ?? {}, [comparison])
  const metricKeys = useMemo(() => {
    const first = Object.values(metrics)[0]
    return first ? Object.keys(first) : []
  }, [metrics])

  async function createExperiment() {
    if (!project || !selectedSpecification || !selectedEnvironment || !canCreate) return
    setBusy(true); setError(null)
    try {
      const created = await experimentService.create(project.id, {
        name: name.trim(),
        operation_ids: selectedOperations,
        environment_id: selectedEnvironment.id,
        approaches: selectedApproaches,
        categories: ['positive', 'negative', 'boundary', 'schema'],
        use_llm: useLlm,
        llm_provider: llmProvider,
        llm_model: llmModel.trim() || undefined,
        llm_candidate_count: llmCandidateCount,
      })
      setName('')
      await refresh()
      setSelectedExperimentId(created.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to start experiment.')
    } finally {
      setBusy(false)
    }
  }

  async function exportComparison() {
    if (!comparison) return
    const blob = new Blob([JSON.stringify(comparison, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${comparison.experiment.name.replace(/[^a-z0-9-_]+/gi, '-')}-comparison.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  async function cancelRun(run: Experiment['runs'][number]) {
    setBusy(true)
    try {
      await campaignService.cancel(run.campaign_id)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to cancel this approach run.')
    } finally {
      setBusy(false)
    }
  }

  return <>
    <PageHeader eyebrow="CONTROLLED EVALUATION" title="Experimental Workbench" description="Run comparable API tests under four explicit generation and selection policies." actions={<Button onClick={() => void refresh()}><RefreshCw size={15} /> Refresh</Button>} />
    {error && <div className="notice notice--warning" role="alert"><strong>Workbench request failed</strong><p>{error}</p><button className="notice__close" onClick={() => setError(null)} aria-label="Dismiss">×</button></div>}
    {!project && <div className="notice notice--info">Select a project to configure an experiment.</div>}
    <Panel title="Experiment setup" subtitle="Every selected approach uses the same OpenAPI version, operations, environment, categories, and per-approach budgets.">
      <div className="notice notice--warning"><div><strong>Use an isolated test target</strong><p>IntelAPI does not reset target state between approach runs. Stateful APIs may carry changes from one run into the next.</p></div></div>
      {!specifications.length && !loading ? <EmptyState title="Import an API first" description="Use API Explorer to import an OpenAPI document before configuring experiments." /> : <div className="resource-form">
        <label htmlFor="experiment-name">Experiment name</label>
        <input id="experiment-name" value={name} onChange={event => setName(event.target.value)} placeholder="e.g. Orders API approach comparison" />
        <label htmlFor="experiment-specification">Specification version</label>
        <select id="experiment-specification" value={specificationId} onChange={event => setSpecificationId(event.target.value)}>
          {specifications.map(specification => <option key={specification.id} value={specification.id}>{specification.name} · {specification.operation_count} operations · {specification.content_sha256.slice(0, 10)}</option>)}
        </select>
        <label htmlFor="experiment-environment">Target environment</label>
        <select id="experiment-environment" value={environmentId} onChange={event => setEnvironmentId(event.target.value)}>
          <option value="">Choose a configured target</option>
          {environments.map(environment => <option key={environment.id} value={environment.id}>{environment.name} · {environment.base_url}</option>)}
        </select>
        {!environments.length && <div className="notice notice--info"><div><strong>No target environments configured</strong><p>Create a project environment with a base URL, then return here to select it.</p><Link to="/environments">Create target environment</Link></div></div>}
        <fieldset className="experiment-approaches"><legend>Approaches</legend>{approachOrder.map(approach => <label className="environment-card" key={approach}><input type="checkbox" checked={selectedApproaches.includes(approach)} onChange={event => setSelectedApproaches(current => event.target.checked ? [...current, approach] : current.filter(item => item !== approach))} /><span className="environment-card__body"><strong>{approachDetails[approach].title}</strong><small>{approachDetails[approach].description}</small></span></label>)}</fieldset>
        <fieldset className="experiment-approaches"><legend>OpenAPI operations ({selectedOperations.length} selected)</legend><div className="resource-list">{operations.map((operation: ApiOperation) => <label className="environment-card" key={operation.id}><input type="checkbox" checked={selectedOperations.includes(operation.id)} onChange={event => setSelectedOperations(current => event.target.checked ? [...current, operation.id] : current.filter(id => id !== operation.id))} /><span className="environment-card__body"><strong>{operation.method.toUpperCase()} {operation.path_template}</strong><small>{operation.summary || operation.operation_key}</small></span></label>)}</div></fieldset>
        <label className="environment-card"><input type="checkbox" checked={useLlm} onChange={event => setUseLlm(event.target.checked)} /><span className="environment-card__body"><strong>Allow configured LLM generation</strong><small>May send selected OpenAPI context and extracted facts to the server configured provider. Disabled runs use deterministic fallback candidates.</small></span></label>
        {useLlm && <><label htmlFor="experiment-llm-provider">LLM provider</label><select id="experiment-llm-provider" value={llmProvider} onChange={event => { const provider = event.target.value as 'nvidia' | 'groq'; setLlmProvider(provider); setLlmModel(llmProviders?.providers.find(item => item.id === provider)?.model ?? '') }}>{llmProviders?.providers.map(provider => <option key={provider.id} value={provider.id}>{provider.id === 'nvidia' ? 'NVIDIA' : 'Groq'}{provider.configured ? ' · configured' : ' · no server key (deterministic fallback)'}</option>)}</select><label htmlFor="experiment-llm-model">Model</label><input id="experiment-llm-model" value={llmModel} maxLength={160} onChange={event => setLlmModel(event.target.value)} placeholder="Configured model" /><label htmlFor="experiment-llm-candidate-count">Maximum LLM candidates per operation</label><select id="experiment-llm-candidate-count" value={llmCandidateCount} onChange={event => setLlmCandidateCount(Number(event.target.value))}>{[3, 4, 5].map(count => <option key={count} value={count}>{count} candidates</option>)}</select></>}
        {!useLlm && selectedApproaches.some(approach => approach === 'llm_baseline' || approach === 'semantic_assisted') && <div className="notice notice--warning"><div><strong>LLM approaches will fall back to deterministic generation</strong><p>This run can compare execution policies, but it will not measure the effect of LLM or semantic prompt context.</p></div></div>}
        <div className="form-actions"><Button variant="primary" disabled={busy || !canCreate} onClick={() => void createExperiment()}><Rocket size={15} /> {busy ? 'Queueing approaches…' : 'Run selected approaches'}</Button></div>
      </div>}
    </Panel>
    <Panel title="Experiment history" subtitle={`${experiments.length} persisted experiment${experiments.length === 1 ? '' : 's'}`}>
      {experiments.length ? <div className="resource-list">{experiments.map(experiment => <button type="button" className={`experiment-history-item${selectedExperimentId === experiment.id ? ' experiment-history-item--active' : ''}`} key={experiment.id} onClick={() => setSelectedExperimentId(experiment.id)}><span><strong>{experiment.name}</strong><small>{new Date(experiment.created_at).toLocaleString()} · {experiment.runs.length} approaches</small></span><Badge tone={tone(experiment.state)}>{experiment.state}</Badge></button>)}</div> : <EmptyState title="No experiments yet" description="Select an API and approaches above to create the first persisted comparison." />}
    </Panel>
    {comparison && <Panel title={`Comparison · ${comparison.experiment.name}`} subtitle={`Specification ${comparison.experiment.configuration.specification_sha256 ?? ''} · ${comparison.experiment.state}`} action={<Button size="sm" onClick={() => void exportComparison()}><Download size={14} /> Export JSON</Button>}>
      <div className="experiment-run-grid">{comparison.experiment.runs.map(run => {
        const inspection = inspections[run.campaign_id]
        const summary = runSummary(run, inspection)
        const rejected = Array.isArray(run.generation_metadata.rejected_candidates)
          ? run.generation_metadata.rejected_candidates as Array<{ kind?: string; index?: number; reason?: string; proposal?: string }>
          : []
        const validCount = Number(run.generation_metadata.valid_candidate_count ?? run.candidate_count)
        const provider = String(run.generation_metadata.llm_provider ?? run.generation_metadata.requested_llm_provider ?? '—')
        const model = String(run.generation_metadata.llm_model ?? run.generation_metadata.requested_llm_model ?? '')
        const generationErrors = Array.isArray(run.generation_metadata.generation_errors)
          ? run.generation_metadata.generation_errors as Array<{ category?: string; message?: string; http_status?: number | null; attempt?: number; failed_generation?: string | null }>
          : []
        return <article className="experiment-run-card" key={run.id}>
          <div><strong>{approachDetails[run.approach].title}</strong><Badge tone={tone(run.state)}>{run.state}</Badge>{(run.state === 'queued' || run.state === 'running') && <Button size="sm" disabled={busy} onClick={() => void cancelRun(run)}>Cancel run</Button>}</div>
          <p>{run.candidate_count} saved candidates · {run.execution_count} executed</p>
          <div className={`experiment-verdict experiment-verdict--${summary.tone}`}><strong>{summary.title}</strong><p>{summary.detail}</p></div>
          <small>{String(run.generation_metadata.mode ?? 'generation pending')} · {String(run.generation_metadata.policy_version ?? '')}</small>
          <small>{provider}{model ? ` · ${model}` : ''} · {validCount} valid · {rejected.filter(item => item.kind === 'candidate').length} rejected</small>
          {Boolean(run.generation_metadata.llm_request_attempted) && <small>{String(run.generation_metadata.requested_candidate_count_per_operation ?? 4)} requested per operation · {Number(run.generation_metadata.retry_count ?? 0)} retries · {Number(run.generation_metadata.attempt_count ?? 0)} attempts · {Number(run.generation_metadata.request_timeout_seconds ?? 30)}s timeout · {String(run.generation_metadata.output_token_budget_per_operation ?? '—')} output tokens</small>}
          {typeof run.generation_metadata.warning === 'string' && <small className="experiment-warning">{run.generation_metadata.warning}</small>}
          {generationErrors.length > 0 && <details className="experiment-rejected"><summary>Provider diagnostics ({generationErrors.length})</summary>{generationErrors.map((item, index) => <div key={`${run.id}-provider-error-${index}`}><p><strong>{item.category ?? 'provider_error'}</strong> · HTTP {item.http_status ?? '—'} · attempt {item.attempt ?? index + 1}</p><p>{item.message ?? 'Provider request failed.'}</p>{item.failed_generation && <pre className="code-preview">{item.failed_generation}</pre>}</div>)}</details>}
          {rejected.length > 0 && <details className="experiment-rejected"><summary>Rejected generation output ({rejected.length})</summary>{rejected.map((item, index) => <div key={`${run.id}-rejected-${index}`}><p>{item.kind === 'candidate' && item.index !== undefined ? `Proposal ${item.index + 1}: ` : ''}{item.reason ?? 'Rejected by candidate validation.'}</p>{item.proposal && <pre className="code-preview">{item.proposal}</pre>}</div>)}</details>}
        </article>
      })}</div>
      {metricKeys.length ? <div className="table-wrap"><table><thead><tr><th>MEASURE</th>{approachOrder.filter(approach => metrics[approach]).map(approach => <th key={approach}>{approachDetails[approach].title}</th>)}</tr></thead><tbody>{metricKeys.map(key => <tr key={key}><th>{key.replaceAll('_', ' ')}</th>{approachOrder.filter(approach => metrics[approach]).map(approach => { const value = metrics[approach][key]; return <td key={approach} title={metricReason(value) ?? undefined}>{metricText(value)}{metricReason(value) && <small className="metric-reason">{metricReason(value)}</small>}</td> })}</tr>)}</tbody></table></div> : <EmptyState title="Comparison is being prepared" description="Metrics load from persisted run, execution, assertion, and finding records." />}
      <div className="resource-list">{comparison.experiment.runs.map(run => {
        const detail = inspections[run.campaign_id]
        const executionsByTest = new Map(detail?.executions.filter(item => item.test_case_id).map(item => [item.test_case_id as string, item]) ?? [])
        return <details className="experiment-inspection" key={run.id}><summary><strong>{approachDetails[run.approach].title} run evidence</strong><small>{detail ? `${detail.tests.length} tests · ${detail.executions.length} requests · ${detail.report.events.length} events` : 'Loading persisted run evidence…'}</small></summary>{detail && <><div className="experiment-evidence-intro"><strong>What this run did</strong><p>Each row is one generated API test. Expand it to see the exact request, expected behavior, target response, and why the result matters.</p></div><div className="campaign-case-list">{detail.tests.map(test => { const execution = executionsByTest.get(test.id); return <details className="campaign-case" key={test.id}><summary><span className="campaign-case__heading"><strong>{test.title}</strong><small>{test.category} · {test.generation_provenance === 'INFERRED' ? 'LLM generated' : 'Rule generated'}</small></span><span className={`execution-status execution-status--${execution?.status ?? 'pending'}`}>{execution?.status ?? 'pending'}</span><span className="muted-cell">{execution ? `${execution.response_status_code ?? execution.error_code ?? 'No status'} · ${execution.duration_ms ?? '—'} ms` : 'Not executed'}</span></summary><div className="campaign-case__details"><div className="experiment-test-meaning"><strong>What this result means</strong><p>{outcomeMeaning(execution)}</p></div><p>{test.description ?? 'No candidate rationale was stored.'}</p><strong>Request sent</strong><pre className="code-preview">{JSON.stringify(test.request_override, null, 2)}</pre>{test.expected_behavior && <><strong>Expected behavior</strong><pre className="code-preview">{JSON.stringify(test.expected_behavior, null, 2)}</pre></>}{execution?.response_body && <><strong>Target response (secrets redacted)</strong><pre className="code-preview">{execution.response_body.slice(0, 6000)}</pre></>}{execution?.error_message && <p className="notice notice--warning">{execution.error_code}: {execution.error_message}</p>}</div></details> })}</div><Panel title="Run timeline" subtitle="Key selection and execution events"><div className="resource-list">{detail.report.events.map(event => <article className="environment-card" key={event.sequence_number}><Badge>{event.sequence_number}</Badge><span className="environment-card__body"><strong>{event.event_type.replaceAll('_', ' ')}</strong><small>{new Date(event.created_at).toLocaleString()}</small></span></article>)}</div></Panel></>}</details>
      })}</div>
      <div className="experiment-metric-guide"><div><BarChart3 size={18} /><strong>How to read this report</strong></div><p><b>Generated candidates</b> are proposed test ideas. <b>Executed requests</b> show which reached the target. A completed HTTP response means the server replied; it is not a correctness verdict unless a matching expected behavior was checked. <b>N/A</b> means the run did not collect enough evidence for that measure; hover its value for the reason.</p></div>
    </Panel>}
  </>
}
