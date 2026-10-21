import { useCallback, useEffect, useState } from 'react'
import { Boxes, Clock3, FolderKanban, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { Button } from '../../components/ui/Button'
import { EmptyState } from '../../components/ui/EmptyState'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { apiRequest } from '../../lib/apiClient'
import { useProject } from '../projects/ProjectContext'
import { workspaceService, type ExecutionRecord } from './workspaceService'

interface Collection { id: string; name: string; description: string | null }
interface Variable { key: string; value: string | null; is_secret: boolean }
interface Environment { id: string; name: string; base_url: string | null; variables: Variable[] }

function ResourceError({ message }: { message: string }) { return <div className="notice notice--warning" role="alert">{message}</div> }

export function CollectionsPage() {
  const { project } = useProject()
  const [items, setItems] = useState<Collection[]>([])
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const load = useCallback(async () => {
    if (!project) return
    setLoading(true); setError(null)
    try { const result = await apiRequest<{ items: Collection[] }>(`/v1/projects/${project.id}/collections`); setItems(result.items) }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to load collections.') }
    finally { setLoading(false) }
  }, [project])
  useEffect(() => { void load() }, [load])
  async function create() {
    if (!project || !name.trim()) return
    try { const created = await apiRequest<Collection>(`/v1/projects/${project.id}/collections`, { method: 'POST', body: JSON.stringify({ name: name.trim(), description: description.trim() || null }) }); setItems((current) => [created, ...current]); setName(''); setDescription('') }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to create collection.') }
  }
  async function remove(item: Collection) {
    try { await apiRequest<void>(`/v1/collections/${item.id}`, { method: 'DELETE' }); setItems((current) => current.filter((row) => row.id !== item.id)) }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to delete collection.') }
  }
  return <>
    <PageHeader eyebrow="REQUEST ORGANIZATION" title="Collections" description="Group related saved requests in your active project." />
    {!project ? <EmptyState title="Select a project" description="Choose or create a project before managing its collections." /> : <>
      {error && <ResourceError message={error} />}
      <Panel title="New collection" subtitle="Collections belong to the active project.">
        <div className="resource-form"><input aria-label="Collection name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Collection name" maxLength={120} /><input aria-label="Description" value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Description (optional)" /><Button variant="primary" disabled={!name.trim()} onClick={() => void create()}><Plus size={15} /> Create collection</Button></div>
      </Panel>
      <Panel title="Your collections" subtitle={`${items.length} collection${items.length === 1 ? '' : 's'}`} action={<Button size="sm" onClick={() => void load()} disabled={loading}><RefreshCw size={14} /> Refresh</Button>}>
        {loading ? <p className="muted-cell">Loading collections…</p> : items.length === 0 ? <EmptyState title="No collections yet" description="Create a collection to organize requests." /> : <div className="resource-list">{items.map((item) => <article key={item.id}><FolderKanban size={18} /><div><strong>{item.name}</strong><p>{item.description || 'No description'}</p></div><Button size="sm" variant="danger" onClick={() => void remove(item)} aria-label={`Delete ${item.name}`}><Trash2 size={14} /></Button></article>)}</div>}
      </Panel>
    </>}
  </>
}

export function EnvironmentsPage() {
  const { project } = useProject()
  const [items, setItems] = useState<Environment[]>([])
  const [name, setName] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [variableKeys, setVariableKeys] = useState<Record<string, string>>({})
  const [variableValues, setVariableValues] = useState<Record<string, string>>({})
  const [secret, setSecret] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const load = useCallback(async () => {
    if (!project) return
    setLoading(true); setError(null)
    try { const result = await apiRequest<{ items: Environment[] }>(`/v1/projects/${project.id}/environments`); setItems(result.items) }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to load environments.') }
    finally { setLoading(false) }
  }, [project])
  useEffect(() => { void load() }, [load])
  async function create() {
    if (!project || !name.trim()) return
    try { const created = await apiRequest<Environment>(`/v1/projects/${project.id}/environments`, { method: 'POST', body: JSON.stringify({ name: name.trim(), base_url: baseUrl.trim() || null }) }); setItems((current) => [created, ...current]); setName(''); setBaseUrl('') }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to create environment.') }
  }
  async function addVariable(environment: Environment) {
    const key = (variableKeys[environment.id] ?? '').trim(); const value = variableValues[environment.id] ?? ''
    if (!key) { setError('Enter a variable key first.'); return }
    try {
      await apiRequest(`/v1/environments/${environment.id}/variables/${encodeURIComponent(key)}`, { method: 'PUT', body: JSON.stringify({ value, is_secret: secret }) })
      setVariableKeys((current) => ({ ...current, [environment.id]: '' })); setVariableValues((current) => ({ ...current, [environment.id]: '' })); setSecret(false); await load()
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save variable.') }
  }
  async function remove(environment: Environment) {
    try { await apiRequest<void>(`/v1/environments/${environment.id}`, { method: 'DELETE' }); setItems((current) => current.filter((item) => item.id !== environment.id)) }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to delete environment.') }
  }
  return <>
    <PageHeader eyebrow="CONFIGURATION" title="Environments" description="Manage base URLs and variables. Secret values are write-only and encrypted by the API." />
    {!project ? <EmptyState title="Select a project" description="Choose or create a project before managing environments." /> : <>
      {error && <ResourceError message={error} />}
      <Panel title="New environment"><div className="resource-form"><input aria-label="Environment name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Environment name" /><input aria-label="Base URL" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://api.example.com" /><Button variant="primary" disabled={!name.trim()} onClick={() => void create()}><Plus size={15} /> Create</Button></div></Panel>
      <Panel title="Project environments" action={<Button size="sm" onClick={() => void load()} disabled={loading}><RefreshCw size={14} /> Refresh</Button>}>
        {loading ? <p className="muted-cell">Loading environments…</p> : items.length === 0 ? <EmptyState title="No environments yet" description="Add an environment for reusable URLs and variables." /> : <div className="resource-list">{items.map((item) => <article className="environment-card" key={item.id}><Boxes size={18} /><div className="environment-card__body"><strong>{item.name}</strong><p>{item.base_url || 'No base URL'} · {item.variables.length} variable{item.variables.length === 1 ? '' : 's'}</p>{item.variables.map((variable) => <small key={variable.key}>{variable.key} = {variable.is_secret ? '•••••• (secret)' : variable.value}</small>)}<div className="resource-form"><input aria-label={`Variable key for ${item.name}`} value={variableKeys[item.id] ?? ''} onChange={(event) => setVariableKeys((current) => ({ ...current, [item.id]: event.target.value }))} placeholder="VARIABLE_KEY" /><input aria-label={`Variable value for ${item.name}`} type={secret ? 'password' : 'text'} value={variableValues[item.id] ?? ''} onChange={(event) => setVariableValues((current) => ({ ...current, [item.id]: event.target.value }))} placeholder="Value" /><label><input type="checkbox" checked={secret} onChange={(event) => setSecret(event.target.checked)} /> Secret</label><Button size="sm" onClick={() => void addVariable(item)}>Save variable</Button></div></div><Button size="sm" variant="danger" onClick={() => void remove(item)} aria-label={`Delete ${item.name}`}><Trash2 size={14} /></Button></article>)}</div>}
      </Panel>
    </>}
  </>
}

export function HistoryPage() {
  const { project } = useProject()
  const [items, setItems] = useState<ExecutionRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const load = useCallback(async () => {
    if (!project) return
    setLoading(true); setError(null)
    try { const result = await workspaceService.listExecutions(project.id); setItems(result.items) }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to load execution history.') }
    finally { setLoading(false) }
  }, [project])
  useEffect(() => { void load() }, [load])
  return <>
    <PageHeader eyebrow="ACTIVITY" title="Request History" description="Persisted executions and their bounded response snapshots." actions={<Button size="sm" onClick={() => void load()} disabled={loading}><RefreshCw size={14} /> Refresh</Button>} />
    {!project ? <EmptyState title="Select a project" description="Choose a project to view its execution history." /> : <Panel title="Executions" subtitle={`${items.length} recent result${items.length === 1 ? '' : 's'}`}>
      {error && <ResourceError message={error} />}{loading ? <p className="muted-cell">Loading history…</p> : items.length === 0 ? <EmptyState title="No executions yet" description="Run a saved request from the API Workspace to see it here." /> : <div className="resource-list">{items.map((item) => <article key={item.id}><Clock3 size={18} /><div><strong>{item.method} {item.url}</strong><p>{item.response_status_code ?? item.error_code ?? item.status} · {item.duration_ms ?? '—'} ms · {new Date(item.created_at).toLocaleString()}</p><small>{item.error_message ?? (item.response_body ?? '').slice(0, 180)}</small></div><span className={`execution-status execution-status--${item.status}`}>{item.status}</span></article>)}</div>}
    </Panel>}
  </>
}
