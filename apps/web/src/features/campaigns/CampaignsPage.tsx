import { useCallback, useEffect, useState } from 'react'
import { FlaskConical, Plus, RefreshCw, Search, Square, StopCircle } from 'lucide-react'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { EmptyState } from '../../components/ui/EmptyState'
import { apiRequest } from '../../lib/apiClient'
import { useProject } from '../projects/ProjectContext'
import { workspaceService, type SavedRequest } from '../workspace/workspaceService'
import { campaignService, type Campaign, type CampaignExecution, type CampaignReport, type CampaignTestCase } from './campaignService'
import { specificationService, type ApiOperation } from '../explorer/specificationService'

const label = (state: Campaign['state']) => state.charAt(0).toUpperCase() + state.slice(1)
const tone = (state: Campaign['state']) => state === 'running' || state === 'queued' ? 'info' : state === 'completed' ? 'success' : state === 'failed' ? 'danger' : 'neutral'

export function CampaignsPage() {
  const { project } = useProject()
  const [items, setItems] = useState<Campaign[]>([])
  const [requests, setRequests] = useState<SavedRequest[]>([])
  const [operations, setOperations] = useState<ApiOperation[]>([])
  const [source, setSource] = useState<'saved_requests' | 'openapi_operations'>('saved_requests')
  const [selectedOperations, setSelectedOperations] = useState<string[]>([])
  const [environments, setEnvironments] = useState<Array<{ id: string; name: string; base_url: string | null }>>([])
  const [environmentId, setEnvironmentId] = useState('')
  const [selectedRequests, setSelectedRequests] = useState<string[]>([])
  const [filter, setFilter] = useState('All')
  const [query, setQuery] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [name, setName] = useState('')
  const [selected, setSelected] = useState('')
  const [report, setReport] = useState<CampaignReport | null>(null)
  const [testCases, setTestCases] = useState<CampaignTestCase[]>([])
  const [executions, setExecutions] = useState<CampaignExecution[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!project) { setItems([]); setRequests([]); return }
    try {
      const [campaigns, saved, environmentResult, specs] = await Promise.all([
        campaignService.list(project.id), workspaceService.listRequests(project.id),
        apiRequest<{ items: Array<{ id: string; name: string; base_url: string | null }> }>(`/v1/projects/${project.id}/environments`),
        specificationService.list(project.id),
      ])
      const operationGroups = await Promise.all(specs.items.map(spec => specificationService.operations(spec.id)))
      setItems(campaigns.items); setRequests(saved.items); setEnvironments(environmentResult.items); setOperations(operationGroups.flatMap(group => group.items)); setError(null)
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to load campaigns.') }
  }, [project])
  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    if (!items.some(item => item.state === 'queued' || item.state === 'running')) return
    const timer = window.setInterval(() => void refresh(), 4000)
    return () => window.clearInterval(timer)
  }, [items, refresh])
  useEffect(() => {
    if (!selected) { setReport(null); setTestCases([]); setExecutions([]); return }
    void Promise.all([campaignService.report(selected), campaignService.tests(selected), campaignService.executions(selected)])
      .then(async ([nextReport, nextCases, firstPage]) => {
        const pages = await Promise.all(Array.from({ length: Math.ceil(Math.max(0, firstPage.total - firstPage.items.length) / firstPage.limit) }, (_, index) => campaignService.executions(selected, firstPage.limit, firstPage.items.length + index * firstPage.limit)))
        setReport(nextReport); setTestCases(nextCases); setExecutions([...firstPage.items, ...pages.flatMap(page => page.items)])
      })
      .catch(err => setError(err instanceof Error ? err.message : 'Unable to load campaign report.'))
  }, [selected, items])

  const visible = items.filter(item => (filter === 'All' || label(item.state) === filter) && `${item.name} ${item.state}`.toLowerCase().includes(query.toLowerCase()))
  async function create() {
    if (!project || !name.trim() || (source === 'saved_requests' ? !selectedRequests.length : !selectedOperations.length)) return
    setBusy(true); setError(null)
    try { const campaign = await campaignService.create(project.id, source === 'saved_requests' ? { name: name.trim(), saved_request_ids: selectedRequests, environment_id: environmentId || null } : { name: name.trim(), operation_ids: selectedOperations, categories: ['positive', 'negative', 'boundary', 'schema'], environment_id: environmentId }); setName(''); setSelectedRequests([]); setSelectedOperations([]); setShowCreate(false); setSelected(campaign.id); await refresh() }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to create campaign.') }
    finally { setBusy(false) }
  }
  async function cancel(campaign: Campaign) {
    setBusy(true)
    try { await campaignService.cancel(campaign.id); await refresh() }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to cancel campaign.') }
    finally { setBusy(false) }
  }

  return <>
    <PageHeader eyebrow="ADAPTIVE TESTING" title="Test Campaigns" description="Queue bounded runs of saved requests and inspect their durable execution timeline." actions={<><Button onClick={() => void refresh()}><RefreshCw size={15} /> Refresh</Button><Button variant="primary" onClick={() => setShowCreate(value => !value)} disabled={!project}><Plus size={15} /> New campaign</Button></>} />
    {error && <div className="notice notice--warning"><span className="notice__icon"><FlaskConical size={16} /></span><div><strong>Request failed</strong><p>{error}</p></div><button className="notice__close" onClick={() => setError(null)} aria-label="Dismiss">×</button></div>}
    {showCreate && <Panel title="Create a bounded campaign" subtitle="Choose saved requests or generate bounded candidates from imported OpenAPI operations."><div className="create-form"><label htmlFor="campaign-name">Campaign name</label><input id="campaign-name" value={name} onChange={event => setName(event.target.value)} placeholder="e.g. Orders API validation" /><label htmlFor="campaign-source">Test source</label><select id="campaign-source" value={source} onChange={event => setSource(event.target.value as typeof source)}><option value="saved_requests">Saved requests</option><option value="openapi_operations">OpenAPI operations</option></select><label htmlFor="campaign-environment">Environment {source === 'openapi_operations' ? '(required)' : ''}</label><select id="campaign-environment" value={environmentId} onChange={event => setEnvironmentId(event.target.value)}><option value="">{source === 'saved_requests' ? 'Use each request’s saved environment' : 'Select an environment'}</option>{environments.map(environment => <option key={environment.id} value={environment.id}>{environment.name} · {environment.base_url ?? 'No base URL'}</option>)}</select><div className="resource-list">{source === 'saved_requests' ? requests.map(request => <label className="environment-card" key={request.id}><input type="checkbox" checked={selectedRequests.includes(request.id)} onChange={event => setSelectedRequests(current => event.target.checked ? [...current, request.id] : current.filter(id => id !== request.id))} /><span className="environment-card__body"><strong>{request.method} {request.name}</strong><small>{request.url_template}</small></span></label>) : operations.map(operation => <label className="environment-card" key={operation.id}><input type="checkbox" checked={selectedOperations.includes(operation.id)} onChange={event => setSelectedOperations(current => event.target.checked ? [...current, operation.id] : current.filter(id => id !== operation.id))} /><span className="environment-card__body"><strong>{operation.method.toUpperCase()} {operation.path_template}</strong><small>{operation.summary || operation.operation_key}</small></span></label>)}{source === 'saved_requests' && requests.length === 0 && <EmptyState title="No saved requests" description="Save a request in the workspace before creating a campaign." />}{source === 'openapi_operations' && operations.length === 0 && <EmptyState title="No imported operations" description="Import an OpenAPI document in Explorer first." />}</div><div className="form-actions"><Button onClick={() => setShowCreate(false)}>Cancel</Button><Button variant="primary" onClick={() => void create()} disabled={busy || !name.trim() || (source === 'saved_requests' ? !selectedRequests.length : !selectedOperations.length || !environmentId || !environments.find(item => item.id === environmentId)?.base_url)}>Queue campaign</Button></div></div></Panel>}
    <div className="filter-toolbar"><div className="filter-pills">{['All','Queued','Running','Completed','Failed','Cancelled'].map(state => <button key={state} className={`filter-pill${filter === state ? ' filter-pill--active' : ''}`} onClick={() => setFilter(state)}>{state}</button>)}</div><Button size="sm" onClick={() => void refresh()}><RefreshCw size={14} /> Refresh status</Button></div>
    <Panel title="Campaigns" subtitle={`${visible.length} campaign${visible.length === 1 ? '' : 's'} shown`} action={<div className="search-field"><Search size={15} /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search campaigns…" aria-label="Search campaigns" /></div>}>
      {visible.length ? <div className="table-wrap"><table><thead><tr><th>CAMPAIGN</th><th>STATUS</th><th>TESTS</th><th>EXECUTIONS</th><th>LAST UPDATED</th><th>ACTION</th></tr></thead><tbody>{visible.map(campaign => <tr key={campaign.id} onClick={() => setSelected(campaign.id)} style={{ cursor: 'pointer' }}><td><div className="campaign-table-name"><span className="campaign-icon"><FlaskConical size={16} /></span><span><strong>{campaign.name}</strong><small>{campaign.id}</small></span></div></td><td><Badge tone={tone(campaign.state)}>{label(campaign.state)}</Badge></td><td className="tabular">{campaign.test_count}</td><td className="tabular">{campaign.execution_count}</td><td className="muted-cell">{new Date(campaign.updated_at).toLocaleString()}</td><td>{campaign.state === 'queued' || campaign.state === 'running' ? <Button size="sm" disabled={busy} onClick={event => { event.stopPropagation(); void cancel(campaign) }}><StopCircle size={14} /> Cancel</Button> : <Button size="sm" onClick={event => { event.stopPropagation(); setSelected(campaign.id) }}><Square size={13} /> Report</Button>}</td></tr>)}</tbody></table></div> : <EmptyState title="No campaigns in this state" description={items.length ? 'Choose a different state filter.' : 'Create a bounded campaign from saved requests.'} action={<Button onClick={() => { setFilter('All'); setShowCreate(true) }}>Create campaign</Button>} />}
    </Panel>
    {report && <><Panel title={`Report · ${report.campaign.name}`} subtitle={`${label(report.campaign.state)} · ${report.tests.executed}/${report.tests.total} tests executed`}><div className="metrics-grid metrics-grid--three"><div className="metric-card"><div className="metric-card__top"><span>Completed executions</span><FlaskConical size={16} /></div><div className="metric-card__value">{report.executions.completed}</div></div><div className="metric-card"><div className="metric-card__top"><span>Failed executions</span><span className="severity-marker severity-marker--high" /></div><div className="metric-card__value">{report.executions.failed}</div></div><div className="metric-card"><div className="metric-card__top"><span>Potential findings</span><span className="severity-marker severity-marker--medium" /></div><div className="metric-card__value">{report.findings.total}</div></div></div>{report.campaign.failure_summary && <div className="notice notice--warning"><strong>{report.campaign.failure_code}</strong><p>{report.campaign.failure_summary}</p></div>}</Panel><Panel title="Generated tests and results" subtitle={`${testCases.length} test cases · ${executions.length} executions loaded`}>
      {testCases.length ? <div className="campaign-case-list">{testCases.map(testCase => { const execution = executions.find(item => item.test_case_id === testCase.id); return <details className="campaign-case" key={testCase.id}><summary><span className="campaign-case__heading"><strong>{testCase.title}</strong><small>{testCase.category} · {testCase.generation_provenance}</small></span><span className={`execution-status execution-status--${execution?.status ?? 'pending'}`}>{execution ? execution.status : 'pending'}</span><span className="muted-cell">{execution ? `${execution.response_status_code ?? execution.error_code ?? 'No status'} · ${execution.duration_ms ?? '—'} ms` : 'Not executed'}</span></summary><div className="campaign-case__details"><p>{testCase.description || 'No additional test description.'}</p><strong>Request variation</strong><pre className="code-preview">{JSON.stringify(testCase.request_override, null, 2)}</pre>{testCase.expected_behavior && <><strong>Expected behavior</strong><pre className="code-preview">{JSON.stringify(testCase.expected_behavior, null, 2)}</pre></>}{execution && <><strong>Execution</strong><p>{execution.method} {execution.url}</p>{execution.error_message && <p className="notice notice--warning">{execution.error_code}: {execution.error_message}</p>}{execution.response_body && <><strong>Response body (redacted)</strong><pre className="code-preview">{execution.response_body.slice(0, 12000)}{execution.response_body.length > 12000 ? '\n… response preview truncated' : ''}</pre></>}</>}</div></details> })}</div> : <EmptyState title="No generated tests" description="The campaign has not produced any test cases." />}
      {report.tests.total > testCases.length && <p className="muted-cell">Showing {testCases.length} of {report.tests.total} test cases.</p>}
      {report.executions.total > executions.length && <p className="muted-cell">Showing {executions.length} of {report.executions.total} executions.</p>}
    </Panel><Panel title="Campaign event timeline" subtitle={`${report.events.length} durable events`}><div className="resource-list">{report.events.map(event => <article className="environment-card" key={event.sequence_number}><Badge>{event.sequence_number}</Badge><div className="environment-card__body"><strong>{event.event_type.replaceAll('_', ' ')}</strong><small>{new Date(event.created_at).toLocaleString()} · {JSON.stringify(event.payload)}</small></div></article>)}</div></Panel></>}
  </>
}
