import { useEffect, useState } from 'react'
import { Clock3, Send } from 'lucide-react'
import { PageHeader } from '../../components/ui/PageHeader'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Panel } from '../../components/ui/Panel'
import { apiRequest } from '../../lib/apiClient'

type Project = { id: string; name: string; description: string | null }
type Execution = {
  id: string; status_code: number; elapsed_ms: number; response_bytes: number
  headers: Record<string, string>; body: unknown; origin: string; outcome: string
  created_at: string
}
type HistoryEntry = {
  id: string; method: string; origin: string; status_code: number | null
  elapsed_ms: number | null; response_bytes: number | null; outcome: string
  error_summary: string | null; created_at: string
}

export function WorkspacePage() {
  const [method, setMethod] = useState('GET')
  const [url, setUrl] = useState('')
  const [headersText, setHeadersText] = useState('{\n  "Accept": "application/json"\n}')
  const [body, setBody] = useState('')
  const [projectId, setProjectId] = useState('')
  const [projects, setProjects] = useState<Project[]>([])
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

  async function sendRequest() {
    setError(''); setResponse(null)
    if (!projectId) { setError('Create or select a project in API Explorer before sending requests.'); return }
    if (unsafe && !window.confirm(`Send this ${method} request to ${url}? It may change remote data.`)) return
    let headers: Record<string, string>
    try {
      headers = JSON.parse(headersText) as Record<string, string>
      if (!headers || Array.isArray(headers) || typeof headers !== 'object' || Object.values(headers).some(value => typeof value !== 'string')) throw new Error('Headers must be a JSON object with string values.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Headers must be valid JSON.'); return }
    setBusy(true)
    try {
      const result = await apiRequest<Execution>(`/v1/projects/${projectId}/executions`, {
        method: 'POST',
        body: JSON.stringify({ method, url, headers, body: body || null, confirm_unsafe: unsafe }),
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
      {history.length ? <div className="divide-y divide-slate-800">{history.map(item => <div key={item.id} className="flex flex-wrap items-center gap-3 p-3 text-xs"><Badge tone={item.status_code && item.status_code < 400 ? 'success' : item.status_code ? 'warning' : 'neutral'}>{item.status_code ?? item.outcome}</Badge><strong>{item.method}</strong><code className="text-slate-400">{item.origin}</code><span className="text-slate-500">{item.elapsed_ms == null ? '—' : `${item.elapsed_ms} ms`}</span><time className="ml-auto text-slate-500">{new Date(item.created_at).toLocaleString()}</time></div>)}</div> : <div className="flex items-center gap-2 p-4 text-xs text-slate-500"><Clock3 size={15} />No request history for this project.</div>}
    </Panel>
  </>
}
