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
  if (state === 'failed' || state === 'partial') return 'danger'
  if (state === 'queued' || state === 'running') return 'info'
  return 'neutral'
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
        {useLlm && <><label htmlFor="experiment-llm-provider">LLM provider</label><select id="experiment-llm-provider" value={llmProvider} onChange={event => { const provider = event.target.value as 'nvidia' | 'groq'; setLlmProvider(provider); setLlmModel(llmProviders?.providers.find(item => item.id === provider)?.model ?? '') }}>{llmProviders?.providers.map(provider => <option key={provider.id} value={provider.id}>{provider.id === 'nvidia' ? 'NVIDIA' : 'Groq'}{provider.configured ? ' · configured' : ' · no server key (deterministic fallback)'}</option>)}</select><label htmlFor="experiment-llm-model">Model</label><input id="experiment-llm-model" value={llmModel} maxLength={160} onChange={event => setLlmModel(event.target.value)} placeholder="Configured model" /></>}
        {!useLlm && selectedApproaches.some(approach => approach === 'llm_baseline' || approach === 'semantic_assisted') && <div className="notice notice--warning"><div><strong>LLM approaches will fall back to deterministic generation</strong><p>This run can compare execution policies, but it will not measure the effect of LLM or semantic prompt context.</p></div></div>}
        <div className="form-actions"><Button variant="primary" disabled={busy || !canCreate} onClick={() => void createExperiment()}><Rocket size={15} /> {busy ? 'Queueing approaches…' : 'Run selected approaches'}</Button></div>
      </div>}
    </Panel>
    <Panel title="Experiment history" subtitle={`${experiments.length} persisted experiment${experiments.length === 1 ? '' : 's'}`}>
      {experiments.length ? <div className="resource-list">{experiments.map(experiment => <button type="button" className={`experiment-history-item${selectedExperimentId === experiment.id ? ' experiment-history-item--active' : ''}`} key={experiment.id} onClick={() => setSelectedExperimentId(experiment.id)}><span><strong>{experiment.name}</strong><small>{new Date(experiment.created_at).toLocaleString()} · {experiment.runs.length} approaches</small></span><Badge tone={tone(experiment.state)}>{experiment.state}</Badge></button>)}</div> : <EmptyState title="No experiments yet" description="Select an API and approaches above to create the first persisted comparison." />}
    </Panel>
    {comparison && <Panel title={`Comparison · ${comparison.experiment.name}`} subtitle={`Specification ${comparison.experiment.configuration.specification_sha256 ?? ''} · ${comparison.experiment.state}`} action={<Button size="sm" onClick={() => void exportComparison()}><Download size={14} /> Export JSON</Button>}>
      <div className="experiment-run-grid">{comparison.experiment.runs.map(run => <article className="experiment-run-card" key={run.id}><div><strong>{approachDetails[run.approach].title}</strong><Badge tone={tone(run.state)}>{run.state}</Badge>{(run.state === 'queued' || run.state === 'running') && <Button size="sm" disabled={busy} onClick={() => void cancelRun(run)}>Cancel run</Button>}</div><p>{run.candidate_count} candidates · {run.execution_count} executed</p><small>{String(run.generation_metadata.mode ?? 'generation pending')} · {String(run.generation_metadata.policy_version ?? '')}</small>{typeof run.generation_metadata.warning === 'string' && <small className="experiment-warning">{run.generation_metadata.warning}</small>}</article>)}</div>
      {metricKeys.length ? <div className="table-wrap"><table><thead><tr><th>MEASURE</th>{approachOrder.filter(approach => metrics[approach]).map(approach => <th key={approach}>{approachDetails[approach].title}</th>)}</tr></thead><tbody>{metricKeys.map(key => <tr key={key}><th>{key.replaceAll('_', ' ')}</th>{approachOrder.filter(approach => metrics[approach]).map(approach => { const value = metrics[approach][key]; return <td key={approach} title={metricReason(value) ?? undefined}>{metricText(value)}{metricReason(value) && <small className="metric-reason">{metricReason(value)}</small>}</td> })}</tr>)}</tbody></table></div> : <EmptyState title="Comparison is being prepared" description="Metrics load from persisted run, execution, assertion, and finding records." />}
      <div className="resource-list">{comparison.experiment.runs.map(run => {
        const detail = inspections[run.campaign_id]
        const executionsByTest = new Map(detail?.executions.filter(item => item.test_case_id).map(item => [item.test_case_id as string, item]) ?? [])
        return <details className="experiment-inspection" key={run.id}><summary><strong>{approachDetails[run.approach].title} run evidence</strong><small>{detail ? `${detail.tests.length} candidates · ${detail.executions.length} requests · ${detail.report.events.length} events` : 'Loading persisted run evidence…'}</small></summary>{detail && <><div className="campaign-case-list">{detail.tests.map(test => { const execution = executionsByTest.get(test.id); return <details className="campaign-case" key={test.id}><summary><span className="campaign-case__heading"><strong>{test.title}</strong><small>{test.category} · {test.generation_provenance}</small></span><span className={`execution-status execution-status--${execution?.status ?? 'pending'}`}>{execution?.status ?? 'pending'}</span><span className="muted-cell">{execution ? `${execution.response_status_code ?? execution.error_code ?? 'No status'} · ${execution.duration_ms ?? '—'} ms` : 'Not executed'}</span></summary><div className="campaign-case__details"><p>{test.description ?? 'No candidate rationale was stored.'}</p><strong>Request candidate</strong><pre className="code-preview">{JSON.stringify(test.request_override, null, 2)}</pre>{test.expected_behavior && <><strong>Declared assertions</strong><pre className="code-preview">{JSON.stringify(test.expected_behavior, null, 2)}</pre></>}{execution?.response_body && <><strong>Redacted response evidence</strong><pre className="code-preview">{execution.response_body.slice(0, 6000)}</pre></>}{execution?.error_message && <p className="notice notice--warning">{execution.error_code}: {execution.error_message}</p>}</div></details> })}</div><Panel title="Selection and execution trace" subtitle="Durable campaign events"><div className="resource-list">{detail.report.events.map(event => <article className="environment-card" key={event.sequence_number}><Badge>{event.sequence_number}</Badge><span className="environment-card__body"><strong>{event.event_type.replaceAll('_', ' ')}</strong><small>{new Date(event.created_at).toLocaleString()} · {JSON.stringify(event.payload)}</small></span></article>)}</div></Panel></>}</details>
      })}</div>
      <div className="notice notice--info"><BarChart3 size={16} /><div><strong>Metric limits are explicit</strong><p>N/A values include the reason that data is unavailable. A completed HTTP response alone does not count as a passed assertion.</p></div></div>
    </Panel>}
  </>
}
