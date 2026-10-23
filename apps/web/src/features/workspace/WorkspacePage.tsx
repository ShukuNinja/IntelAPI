import { useEffect, useState } from 'react'
import { Clock3, Send } from 'lucide-react'
import { PageHeader } from '../../components/ui/PageHeader'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Panel } from '../../components/ui/Panel'
import { apiRequest } from '../../lib/apiClient'

type Project = { id: string; name: string; description: string | null }
type SavedRequest = { id: string; name: string; collection_name: string | null; method: string; url: string; headers: Record<string, string>; body: string | null }
type Environment = { id: string; name: string; base_url: string | null; variables: Record<string, string>; secrets: Record<string, { has_value: boolean }> }
type Execution = {
  id: string; status_code: number; elapsed_ms: number; response_bytes: number
  headers: Record<string, string>; body: unknown; origin: string; outcome: string
  created_at: string
}
type HistoryEntry = {
  id: string; method: string; origin: string; status_code: number | null
  elapsed_ms: number | null; response_bytes: number | null; outcome: string
  error_summary: string | null; created_at: string
  candidate_id?: string | null
}

export function WorkspacePage() {
  const [method, setMethod] = useState('GET')
  const [url, setUrl] = useState('')
  const [headersText, setHeadersText] = useState('{\n  "Accept": "application/json"\n}')
  const [body, setBody] = useState('')
  const [projectId, setProjectId] = useState('')
  const [projects, setProjects] = useState<Project[]>([])
  const [savedRequests, setSavedRequests] = useState<SavedRequest[]>([])
  const [environments, setEnvironments] = useState<Environment[]>([])
  const [selectedRequestId, setSelectedRequestId] = useState('')
  const [selectedEnvironmentId, setSelectedEnvironmentId] = useState('')
  const [requestName, setRequestName] = useState('')
  const [collectionName, setCollectionName] = useState('')
  const [newEnvironmentName, setNewEnvironmentName] = useState('')
  const [newEnvironmentBaseUrl, setNewEnvironmentBaseUrl] = useState('')
  const [newEnvironmentVariables, setNewEnvironmentVariables] = useState('{\n  "region": "us-east-1"\n}')
  const [newEnvironmentSecrets, setNewEnvironmentSecrets] = useState('{}')
  const [showEnvironmentForm, setShowEnvironmentForm] = useState(false)
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [response, setResponse] = useState<Execution | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const unsafe = !['GET', 'HEAD', 'OPTIONS'].includes(method)

  async function refreshHistory(id: string) {
    if (!id) { setHistory([]); return }
    setHistory(await apiRequest<HistoryEntry[]>(`/v1/projects/${id}/executions`))
  }

  useEffect(() => {
    void apiRequest<Project[]>('/v1/projects').then(items => {
      setProjects(items)
      if (items[0]) setProjectId(items[0].id)
    }).catch(cause => setError(cause instanceof Error ? cause.message : 'Unable to load projects.'))
  }, [])

  useEffect(() => {
    void refreshHistory(projectId).catch(cause => setError(cause instanceof Error ? cause.message : 'Unable to load request history.'))
  }, [projectId])

  useEffect(() => {
    if (!projectId) { setSavedRequests([]); setEnvironments([]); setSelectedEnvironmentId(''); return }
    void Promise.all([
      apiRequest<SavedRequest[]>(`/v1/projects/${projectId}/saved-requests`),
      apiRequest<Environment[]>(`/v1/projects/${projectId}/environments`),
    ]).then(([requests, envs]) => { setSavedRequests(requests); setEnvironments(envs) })
      .catch(cause => setError(cause instanceof Error ? cause.message : 'Unable to load saved requests and environments.'))
  }, [projectId])

  function applySavedRequest(id: string) {
    setSelectedRequestId(id)
    const saved = savedRequests.find(item => item.id === id)
    if (!saved) return
    setMethod(saved.method)
    setUrl(saved.url)
    setHeadersText(JSON.stringify(saved.headers, null, 2))
    setBody(saved.body ?? '')
    setRequestName(saved.name)
    setCollectionName(saved.collection_name ?? '')
  }

  async function saveRequest() {
    if (!projectId) { setError('Select a project before saving a request.'); return }
    if (!requestName.trim()) { setError('Enter a name for this request.'); return }
    let headers: Record<string, string>
    try {
      headers = JSON.parse(headersText) as Record<string, string>
      if (!headers || Array.isArray(headers) || typeof headers !== 'object' || Object.values(headers).some(value => typeof value !== 'string')) throw new Error('Headers must be a JSON object with string values.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Headers must be valid JSON.'); return }
    try {
      const saved = await apiRequest<SavedRequest>(`/v1/projects/${projectId}/saved-requests${selectedRequestId ? `/${selectedRequestId}` : ''}`, {
        method: selectedRequestId ? 'PUT' : 'POST',
        body: JSON.stringify({ name: requestName.trim(), collection_name: collectionName.trim() || null, method, url, headers, body: body || null }),
      })
      setSavedRequests(current => [...current.filter(item => item.id !== saved.id), saved].sort((a, b) => (a.collection_name ?? '').localeCompare(b.collection_name ?? '') || a.name.localeCompare(b.name)))
      setSelectedRequestId(saved.id)
      setError('')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to save the request.') }
  }

  async function createEnvironment() {
    if (!projectId || !newEnvironmentName.trim()) { setError('Select a project and enter an environment name.'); return }
    let variables: Record<string, string>
    let secrets: Record<string, string>
    try {
      variables = JSON.parse(newEnvironmentVariables) as Record<string, string>
      if (!variables || Array.isArray(variables) || typeof variables !== 'object' || Object.values(variables).some(value => typeof value !== 'string')) throw new Error('Variables must be a JSON object with string values.')
      secrets = JSON.parse(newEnvironmentSecrets) as Record<string, string>
      if (!secrets || Array.isArray(secrets) || typeof secrets !== 'object' || Object.values(secrets).some(value => typeof value !== 'string')) throw new Error('Secret values must be a JSON object with string values.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Environment variables must be valid JSON.'); return }
    try {
      const environment = await apiRequest<Environment>(`/v1/projects/${projectId}/environments`, {
        method: 'POST', body: JSON.stringify({ name: newEnvironmentName.trim(), base_url: newEnvironmentBaseUrl.trim() || null, variables, secrets }),
      })
      setEnvironments(current => [...current.filter(item => item.id !== environment.id), environment].sort((a, b) => a.name.localeCompare(b.name)))
      setSelectedEnvironmentId(environment.id)
      setNewEnvironmentName('')
      setNewEnvironmentBaseUrl('')
      setNewEnvironmentSecrets('{}')
      setShowEnvironmentForm(false)
      setError('')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to save the environment.') }
  }

  async function sendRequest() {
    setError(''); setResponse(null)
    if (!projectId) { setError('Create or select a project in API Explorer before sending requests.'); return }
    let headers: Record<string, string>
    try {
      headers = JSON.parse(headersText) as Record<string, string>
      if (!headers || Array.isArray(headers) || typeof headers !== 'object' || Object.values(headers).some(value => typeof value !== 'string')) throw new Error('Headers must be a JSON object with string values.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Headers must be valid JSON.'); return }
    if (unsafe && !window.confirm(`Send this ${method} request to ${url}? It may change remote data.`)) return
    setBusy(true)
    try {
      const result = await apiRequest<Execution>(`/v1/projects/${projectId}/executions`, {
        method: 'POST',
        body: JSON.stringify({ method, url, headers, body: body || null, confirm_unsafe: unsafe, environment_id: selectedEnvironmentId || null }),
      })
      setResponse(result)
      await refreshHistory(projectId)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'The request could not be completed.') }
    finally { setBusy(false) }
  }

  return <>
    <PageHeader eyebrow="REQUEST BUILDER" title="API Workspace" description="Send bounded requests, inspect real responses, and review project execution history."
      actions={<Button variant="primary" onClick={() => void sendRequest()} disabled={busy || !url.trim()}><Send size={15} />{busy ? 'Sending…' : 'Send request'}</Button>} />
    <Panel title="Request" subtitle="Requests are sent by the backend with timeout, response-size, redirect, and target-network controls.">
      <div className="grid gap-4 p-4">
        <label className="text-xs text-slate-300">Project<select className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm" value={projectId} onChange={event => setProjectId(event.target.value)}><option value="">Select a project…</option>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>
        <div className="grid gap-3 rounded-lg border border-slate-800 bg-slate-950/50 p-3 md:grid-cols-[1fr_1fr_auto]"><label className="text-xs text-slate-300">Saved request<select className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm" value={selectedRequestId} onChange={event => applySavedRequest(event.target.value)}><option value="">New request…</option>{savedRequests.map(item => <option key={item.id} value={item.id}>{item.collection_name ? `${item.collection_name} / ` : ''}${item.name}</option>)}</select></label><label className="text-xs text-slate-300">Environment<select className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm" value={selectedEnvironmentId} onChange={event => setSelectedEnvironmentId(event.target.value)}><option value="">No environment</option>{environments.map(item => <option key={item.id} value={item.id}>{item.name}{Object.keys(item.secrets ?? {}).length ? ` · ${Object.keys(item.secrets).length} secret(s)` : ''}</option>)}</select></label><div className="flex items-end"><Button size="sm" onClick={() => { setShowEnvironmentForm(value => !value); setError('') }}>{showEnvironmentForm ? 'Close' : 'New environment'}</Button></div>
          <div className="grid gap-2 md:col-span-3 md:grid-cols-[1fr_1fr_auto]"><input aria-label="Saved request name" className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs" value={requestName} onChange={event => setRequestName(event.target.value)} placeholder="Request name"/><input aria-label="Collection name" className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs" value={collectionName} onChange={event => setCollectionName(event.target.value)} placeholder="Collection (optional)"/><Button size="sm" onClick={() => void saveRequest()}>{selectedRequestId ? 'Update saved request' : 'Save request'}</Button></div>
          {showEnvironmentForm && <div className="grid gap-2 border-t border-slate-800 pt-3 md:col-span-3 md:grid-cols-2"><input aria-label="Environment name" className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs" value={newEnvironmentName} onChange={event => setNewEnvironmentName(event.target.value)} placeholder="Environment name"/><input aria-label="Environment base URL" className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs" value={newEnvironmentBaseUrl} onChange={event => setNewEnvironmentBaseUrl(event.target.value)} placeholder="Base URL, e.g. http://localhost:8000"/><textarea aria-label="Environment variables" className="min-h-20 rounded border border-slate-700 bg-slate-900 p-2 font-mono text-xs md:col-span-2" value={newEnvironmentVariables} onChange={event => setNewEnvironmentVariables(event.target.value)} /><textarea aria-label="Write-only environment secrets" className="min-h-20 rounded border border-slate-700 bg-slate-900 p-2 font-mono text-xs md:col-span-2" value={newEnvironmentSecrets} onChange={event => setNewEnvironmentSecrets(event.target.value)} placeholder={'{"token":"paste-secret-here"}'} /><div className="flex items-center justify-between text-[11px] text-slate-500 md:col-span-2"><span>Use {'{{baseUrl}}'} and {'{{variableName}}'} in requests. Secrets are encrypted server-side and never returned.</span><Button size="sm" variant="primary" onClick={() => void createEnvironment()}>Save environment</Button></div></div>}
        </div>
        <div className="grid gap-2 sm:grid-cols-[130px_1fr]"><select className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm" aria-label="HTTP method" value={method} onChange={event => setMethod(event.target.value)}>{['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'].map(value => <option key={value}>{value}</option>)}</select><input className="rounded border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm" aria-label="Request URL" value={url} onChange={event => setUrl(event.target.value)} placeholder="http://localhost:8000/api/resource" spellCheck={false} /></div>
        {unsafe && <p className="m-0 text-xs text-amber-300">Sending {method} can change target data. The app asks for confirmation before sending.</p>}
        <label className="text-xs text-slate-300">Headers (JSON object)<textarea className="mt-1 min-h-24 w-full rounded border border-slate-700 bg-slate-950 p-3 font-mono text-xs" value={headersText} onChange={event => setHeadersText(event.target.value)} spellCheck={false} /></label>
        <label className="text-xs text-slate-300">Request body<textarea className="mt-1 min-h-36 w-full rounded border border-slate-700 bg-slate-950 p-3 font-mono text-xs" value={body} onChange={event => setBody(event.target.value)} spellCheck={false} placeholder="Optional request body" /></label>
        {error && <p role="alert" className="m-0 text-xs text-rose-300">{error}</p>}
      </div>
    </Panel>
    <Panel title="Response" subtitle="Actual response returned by the selected target." action={response ? <Badge tone={response.status_code < 400 ? 'success' : 'warning'}>{response.status_code}</Badge> : <Badge>Not sent</Badge>}>
      {response ? <div className="grid gap-3 p-4"><div className="flex flex-wrap gap-4 text-xs text-slate-400"><span>TIME <strong className="text-slate-100">{response.elapsed_ms} ms</strong></span><span>SIZE <strong className="text-slate-100">{response.response_bytes} bytes</strong></span><span>ORIGIN <strong className="text-slate-100">{response.origin}</strong></span></div><pre className="max-h-[32rem] overflow-auto rounded-lg border border-slate-800 bg-slate-950 p-4 text-xs text-slate-200">{JSON.stringify(response.body, null, 2)}</pre><details><summary className="cursor-pointer text-xs text-slate-400">Response headers</summary><pre className="mt-2 text-xs text-slate-400">{JSON.stringify(response.headers, null, 2)}</pre></details></div> : <div className="p-5 text-xs text-slate-500">Send a request to see its real response here.</div>}
    </Panel>
    <Panel title="Recent executions" subtitle="History stores status and timing metadata. Request credentials and response bodies are not persisted.">
      {history.length ? <div className="divide-y divide-slate-800">{history.map(item => <div key={item.id} className="flex flex-wrap items-center gap-3 p-3 text-xs"><Badge tone={item.status_code && item.status_code < 400 ? 'success' : item.status_code ? 'warning' : 'neutral'}>{item.status_code ?? item.outcome}</Badge><strong>{item.method}</strong><code className="text-slate-400">{item.origin}</code>{item.candidate_id && <Badge tone="info">Candidate {item.candidate_id}</Badge>}<span className="text-slate-500">{item.elapsed_ms == null ? '—' : `${item.elapsed_ms} ms`}</span><time className="ml-auto text-slate-500">{new Date(item.created_at).toLocaleString()}</time></div>)}</div> : <div className="flex items-center gap-2 p-4 text-xs text-slate-500"><Clock3 size={15} />No request history for this project.</div>}
    </Panel>
  </>
}
