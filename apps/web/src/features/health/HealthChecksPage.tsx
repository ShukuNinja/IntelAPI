import { useCallback, useEffect, useState } from 'react'
import { Activity, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { EmptyState } from '../../components/ui/EmptyState'
import { apiRequest } from '../../lib/apiClient'
import { useProject } from '../projects/ProjectContext'
import { workspaceService, type SavedRequest } from '../workspace/workspaceService'
import { healthService, type HealthAssertionType, type HealthCheck, type HealthRun } from './healthService'

export function HealthChecksPage() {
  const { project } = useProject()
  const [items, setItems] = useState<HealthCheck[]>([])
  const [requests, setRequests] = useState<SavedRequest[]>([])
  const [lastRuns, setLastRuns] = useState<Record<string, HealthRun>>({})
  const [showCreate, setShowCreate] = useState(false)
  const [name, setName] = useState('')
  const [requestId, setRequestId] = useState('')
  const [assertionType, setAssertionType] = useState<HealthAssertionType>('status_code')
  const [assertionTarget, setAssertionTarget] = useState('')
  const [assertionExpected, setAssertionExpected] = useState('200')
  const [busyId, setBusyId] = useState('')
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!project) { setItems([]); setRequests([]); return }
    try {
      const [checks, saved] = await Promise.all([healthService.list(project.id), workspaceService.listRequests(project.id)])
      setItems(checks.items); setRequests(saved.items); setError(null)
      const histories = await Promise.all(checks.items.map(async check => {
        try {
          const results = await healthService.results(check.id)
          const executionId = results[0]?.execution_id
          if (!executionId) return null
          const latest = results.filter(item => item.execution_id === executionId)
          return [check.id, { health_check: check, execution_id: executionId,
            status: results[0]?.execution_status === 'failed' ? 'unavailable' as const : latest.every(item => item.passed) ? 'healthy' as const : 'degraded' as const,
            assertions: latest } satisfies HealthRun] as const
        } catch { return null }
      }))
      setLastRuns(Object.fromEntries(histories.filter((item): item is NonNullable<typeof item> => item !== null)))
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to load health checks.') }
  }, [project])
  useEffect(() => { void refresh() }, [refresh])

  async function create() {
    if (!project || !name.trim() || !requestId) return
    setBusyId('create'); setError(null)
    try {
      const numeric = assertionType === 'status_code' || assertionType === 'response_time_lte'
      const structured = assertionType === 'json_path_equals' || assertionType === 'response_schema'
      let expected: unknown = assertionExpected
      if (numeric) expected = Number(assertionExpected)
      if (structured) expected = JSON.parse(assertionExpected) as unknown
      if (assertionType === 'response_schema' && (!expected || typeof expected !== 'object' || Array.isArray(expected))) throw new Error('Response schema must be a JSON object.')
      if ((assertionType === 'json_path_equals' || assertionType === 'header_equals') && !assertionTarget.trim()) throw new Error('Enter the assertion target.')
      await healthService.create(project.id, name.trim(), requestId, {
        type: assertionType,
        expected,
        ...(assertionType === 'json_path_equals' || assertionType === 'header_equals' ? { target: assertionTarget.trim() } : {}),
      })
      setName(''); setShowCreate(false); await refresh()
    }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to create health check.') }
    finally { setBusyId('') }
  }
  async function run(check: HealthCheck) {
    setBusyId(check.id); setError(null)
    try { const result = await healthService.run(check.id); setLastRuns(current => ({ ...current, [check.id]: result })) }
    catch (err) { setError(err instanceof Error ? err.message : 'Health check failed.') }
    finally { setBusyId('') }
  }
  async function remove(check: HealthCheck) {
    if (!window.confirm(`Delete health check “${check.name}”?`)) return
    setBusyId(check.id)
    try { await fetchDelete(check.id); await refresh() }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to delete health check.') }
    finally { setBusyId('') }
  }

  return <>
    <PageHeader eyebrow="OBSERVABILITY" title="Health Checks" description="Run saved requests against persisted assertions and review their recorded results." actions={<><Button onClick={() => void refresh()}><RefreshCw size={15} /> Refresh</Button><Button variant="primary" disabled={!project || requests.length === 0} onClick={() => setShowCreate(value => !value)}><Plus size={15} /> Add check</Button></>} />
    {error && <div className="notice notice--warning"><span className="notice__icon"><Activity size={16} /></span><div><strong>Request failed</strong><p>{error}</p></div><button className="notice__close" onClick={() => setError(null)} aria-label="Dismiss">×</button></div>}
    {showCreate && <Panel title="Create a health check" subtitle="Choose an explicit assertion and persist its outcome on each run.">
      <div className="resource-form">
        <input aria-label="Health check name" value={name} onChange={event => setName(event.target.value)} placeholder="Check name" />
        <select aria-label="Saved request" value={requestId} onChange={event => setRequestId(event.target.value)}><option value="">Choose a saved request</option>{requests.map(request => <option key={request.id} value={request.id}>{request.method} {request.name} · {request.url_template}</option>)}</select>
        <select aria-label="Assertion type" value={assertionType} onChange={event => { const value = event.target.value as HealthAssertionType; setAssertionType(value); setAssertionExpected(value === 'status_code' ? '200' : value === 'response_schema' ? '{\n  "type": "object"\n}' : '') }}>
          <option value="status_code">HTTP status code</option><option value="response_time_lte">Latency threshold (ms)</option><option value="json_path_equals">JSON path value</option><option value="header_equals">Response header</option><option value="response_schema">Response schema</option>
        </select>
        {(assertionType === 'json_path_equals' || assertionType === 'header_equals') && <input aria-label={assertionType === 'json_path_equals' ? 'JSON path' : 'Header name'} value={assertionTarget} onChange={event => setAssertionTarget(event.target.value)} placeholder={assertionType === 'json_path_equals' ? '$.data.status' : 'content-type'} />}
        {assertionType === 'response_schema' ? <textarea aria-label="Expected response schema" rows={7} value={assertionExpected} onChange={event => setAssertionExpected(event.target.value)} spellCheck={false} /> : <input aria-label={assertionType === 'status_code' ? 'Expected status code' : assertionType === 'response_time_lte' ? 'Maximum latency in milliseconds' : 'Expected value (JSON)'} type={assertionType === 'status_code' || assertionType === 'response_time_lte' ? 'number' : 'text'} min={assertionType === 'status_code' ? 100 : 0} max={assertionType === 'status_code' ? 599 : undefined} value={assertionExpected} onChange={event => setAssertionExpected(event.target.value)} placeholder={assertionType === 'json_path_equals' ? '"ready"' : 'Expected value'} />}
        <Button variant="primary" disabled={busyId === 'create' || !name.trim() || !requestId} onClick={() => void create()}>Save check</Button>
      </div>
    </Panel>}
    <div className="metrics-grid metrics-grid--three"><div className="metric-card"><div className="metric-card__top"><span>Configured checks</span><Activity size={16} /></div><div className="metric-card__value">{items.length}</div><div className="metric-card__foot"><span className="metric-period">Saved in this project</span></div></div><div className="metric-card"><div className="metric-card__top"><span>Healthy last run</span><span className="status-dot status-dot--green" /></div><div className="metric-card__value">{Object.values(lastRuns).filter(runResult => runResult.status === 'healthy').length}</div><div className="metric-card__foot"><span className="metric-period">This session</span></div></div><div className="metric-card"><div className="metric-card__top"><span>Needs attention</span><span className="status-dot status-dot--amber" /></div><div className="metric-card__value">{Object.values(lastRuns).filter(runResult => runResult.status !== 'healthy').length}</div><div className="metric-card__foot"><span className="metric-period">This session</span></div></div></div>
    <Panel title="Configured endpoint checks" subtitle={`${items.length} persisted check${items.length === 1 ? '' : 's'}`}>
      {items.length === 0 ? <EmptyState title="No health checks yet" description={requests.length ? 'Add a check for any saved request in this project.' : 'Save a request in the workspace before creating a health check.'} /> : <div className="table-wrap"><table><thead><tr><th>CHECK</th><th>LAST RESULT</th><th>ASSERTIONS</th><th>ACTIONS</th></tr></thead><tbody>{items.map(check => { const runResult = lastRuns[check.id]; const request = requests.find(item => item.id === check.saved_request_id); return <tr key={check.id}><td><div className="endpoint-cell"><span>{request?.method ?? '—'}</span><span>{check.name}<small>{request?.url_template ?? 'Request unavailable'}</small></span></div></td><td>{runResult ? <Badge tone={runResult.status === 'healthy' ? 'success' : runResult.status === 'degraded' ? 'warning' : 'danger'}>{runResult.status}</Badge> : <Badge>Not run</Badge>}</td><td className="tabular">{runResult ? `${runResult.assertions.filter(item => item.passed).length}/${runResult.assertions.length} passed` : check.definition.assertions.length}</td><td><Button size="sm" disabled={busyId === check.id || !check.enabled} onClick={() => void run(check)}>{busyId === check.id ? 'Running…' : 'Run check'}</Button> <Button size="sm" variant="danger" disabled={busyId === check.id} aria-label={`Delete ${check.name}`} onClick={() => void remove(check)}><Trash2 size={14} /></Button></td></tr> })}</tbody></table></div>}
    </Panel>
    {Object.entries(lastRuns).map(([checkId, result]) => <Panel key={checkId} title={`Latest results · ${result.health_check.name}`} subtitle={`Execution ${result.execution_id}`}><div className="resource-list">{result.assertions.map(item => <article className="environment-card" key={item.id}><div className="environment-card__body"><strong>{item.message}</strong><small>Expected: {JSON.stringify(item.expected)} · Actual: {JSON.stringify(item.actual)}</small></div><Badge tone={item.passed ? 'success' : 'danger'}>{item.passed ? 'Passed' : 'Failed'}</Badge></article>)}</div></Panel>)}
  </>
}

async function fetchDelete(id: string) {
  return apiRequest<void>(`/v1/health-checks/${id}`, { method: 'DELETE' })
}
