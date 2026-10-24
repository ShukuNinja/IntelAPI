import { useCallback, useEffect, useState } from 'react'
import { Boxes, FolderKanban, Plus, Save, Trash2 } from 'lucide-react'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { apiRequest } from '../../lib/apiClient'
import { useProjectWorkspace } from '../projects/ProjectWorkspaceContext'

type Collection = { id: string; name: string; description: string | null }
type Environment = { id: string; name: string; base_url: string | null; variables: Record<string, string>; secrets: Record<string, { has_value: boolean }> }

export function ResourceManagementPage({ kind }: { kind: 'collections' | 'environments' }) {
  const collectionsMode = kind === 'collections'
  const { projects, activeProjectId: projectId, setActiveProjectId } = useProjectWorkspace()
  const [collections, setCollections] = useState<Collection[]>([])
  const [environments, setEnvironments] = useState<Environment[]>([])
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [variablesText, setVariablesText] = useState('{}')
  const [secretsText, setSecretsText] = useState('{}')
  const [removeSecretsText, setRemoveSecretsText] = useState('')
  const [editingId, setEditingId] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const root = projectId ? `/v1/projects/${projectId}` : ''

  useEffect(() => {
    setEditingId(''); setName(''); setDescription(''); setBaseUrl('')
    setVariablesText('{}'); setSecretsText('{}'); setRemoveSecretsText('')
    setError(''); setNotice('')
  }, [projectId])

  const loadResources = useCallback(async () => {
    if (!root) { setCollections([]); setEnvironments([]); return }
    try {
      if (collectionsMode) setCollections(await apiRequest<Collection[]>(`${root}/collections`))
      else setEnvironments(await apiRequest<Environment[]>(`${root}/environments`))
      setError('')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : `Unable to load ${kind}.`)
    }
  }, [collectionsMode, kind, root])

  useEffect(() => { void loadResources() }, [loadResources])

  function resetForm() {
    setEditingId(''); setName(''); setDescription(''); setBaseUrl('')
    setVariablesText('{}'); setSecretsText('{}'); setRemoveSecretsText('')
  }

  function editCollection(item: Collection) {
    setEditingId(item.id); setName(item.name); setDescription(item.description ?? '')
  }
  function editEnvironment(item: Environment) {
    setEditingId(item.id); setName(item.name); setBaseUrl(item.base_url ?? '')
    setVariablesText(JSON.stringify(item.variables, null, 2)); setSecretsText('{}'); setRemoveSecretsText('')
  }

  async function save() {
    if (!root || !name.trim()) return
    setBusy(true); setError(''); setNotice('')
    try {
      let body: Record<string, unknown>
      let endpoint: string
      if (collectionsMode) {
        body = { name: name.trim(), description: description.trim() || null }
        endpoint = `${root}/collections${editingId ? `/${editingId}` : ''}`
      } else {
        const variables = JSON.parse(variablesText) as Record<string, string>
        const secrets = JSON.parse(secretsText) as Record<string, string>
        const remove_secrets = removeSecretsText.split(',').map(value => value.trim()).filter(Boolean)
        body = { name: name.trim(), base_url: baseUrl.trim() || null, variables, secrets, remove_secrets }
        endpoint = `${root}/environments${editingId ? `/${editingId}` : ''}`
      }
      await apiRequest(endpoint, { method: editingId ? 'PUT' : 'POST', body: JSON.stringify(body) })
      setNotice(editingId ? 'Changes saved.' : 'Resource created.')
      resetForm(); await loadResources()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to save changes.')
    } finally { setBusy(false) }
  }

  async function remove(id: string) {
    if (!root) return
    setBusy(true); setError(''); setNotice('')
    try {
      await apiRequest(`${root}/${collectionsMode ? 'collections' : 'environments'}/${id}`, { method: 'DELETE' })
      if (editingId === id) resetForm()
      setNotice('Resource deleted.'); await loadResources()
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to delete resource.') }
    finally { setBusy(false) }
  }

  return <>
    <PageHeader eyebrow={collectionsMode ? 'REQUEST ORGANIZATION' : 'CONFIGURATION'} title={collectionsMode ? 'Collections' : 'Environments'} description={collectionsMode ? 'Create and maintain project-owned groups for saved requests.' : 'Manage project base URLs, public variables, and encrypted write-only secrets.'} />
    {error && <p role="alert" className="mb-3 rounded border border-rose-900 bg-rose-950/40 p-3 text-sm text-rose-200">{error}</p>}
    {notice && <p role="status" className="mb-3 rounded border border-emerald-900 bg-emerald-950/30 p-3 text-sm text-emerald-200">{notice}</p>}
    <Panel title="Project" subtitle="Collections and environments are scoped to the selected project.">
      <div className="p-4"><label className="block max-w-xl text-xs text-slate-300">Project<select className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 p-2" value={projectId} onChange={event => { setActiveProjectId(event.target.value); setEditingId(''); setError(''); setNotice('') }}>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>{projects.length === 0 && <p className="mb-0 text-xs text-slate-500">Use the New project button in the app header before adding {kind}.</p>}</div>
    </Panel>
    <Panel title={editingId ? `Edit ${collectionsMode ? 'collection' : 'environment'}` : `New ${collectionsMode ? 'collection' : 'environment'}`}>
      <div className="grid gap-3 p-4 md:grid-cols-2">
        <label className="text-xs text-slate-300">Name<input aria-label="Resource name" className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 p-2" value={name} onChange={event => setName(event.target.value)} /></label>
        {collectionsMode ? <label className="text-xs text-slate-300">Description<input aria-label="Collection description" className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 p-2" value={description} onChange={event => setDescription(event.target.value)} /></label> : <label className="text-xs text-slate-300">Base URL<input aria-label="Environment base URL" className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 p-2 font-mono" value={baseUrl} onChange={event => setBaseUrl(event.target.value)} placeholder="http://localhost:8000" /></label>}
        {!collectionsMode && <><label className="text-xs text-slate-300 md:col-span-2">Public variables · JSON<textarea aria-label="Environment variables JSON" className="mt-1 block min-h-24 w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs" value={variablesText} onChange={event => setVariablesText(event.target.value)} /></label><label className="text-xs text-slate-300 md:col-span-2">Write-only secrets · JSON<textarea aria-label="Environment secrets JSON" className="mt-1 block min-h-20 w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs" value={secretsText} onChange={event => setSecretsText(event.target.value)} placeholder="{}" /><span className="mt-1 block text-[10px] text-slate-500">Secret values are encrypted server-side. Existing values are never returned to this page.</span></label>{editingId && <label className="text-xs text-slate-300 md:col-span-2">Remove secret names · comma separated<input aria-label="Secrets to remove" className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 p-2" value={removeSecretsText} onChange={event => setRemoveSecretsText(event.target.value)} /></label>}</>}
        <div className="flex gap-2"><Button variant="primary" disabled={busy || !projectId || !name.trim()} onClick={() => void save()}>{editingId ? <Save size={14} /> : <Plus size={14} />}{editingId ? 'Save changes' : 'Create'}</Button>{editingId && <Button disabled={busy} onClick={resetForm}>Cancel</Button>}</div>
      </div>
    </Panel>
    <Panel title={collectionsMode ? 'Saved collections' : 'Saved environments'} subtitle="Changes are stored in PostgreSQL and reload when the page is refreshed.">
      {collectionsMode ? collections.length === 0 ? <div className="p-4 text-xs text-slate-500">No collections in this project yet.</div> : <div className="divide-y divide-slate-800">{collections.map(item => <div key={item.id} className="flex flex-wrap items-center gap-3 p-3"><FolderKanban size={15} className="text-cyan-400" /><div className="min-w-0 flex-1"><strong className="text-xs">{item.name}</strong><p className="mb-0 mt-1 text-[10px] text-slate-500">{item.description || 'No description'}</p></div><Button size="sm" onClick={() => editCollection(item)}>Edit</Button><Button size="sm" variant="danger" disabled={busy} onClick={() => void remove(item.id)}><Trash2 size={13} /> Delete</Button></div>)}</div> : environments.length === 0 ? <div className="p-4 text-xs text-slate-500">No environments in this project yet.</div> : <div className="divide-y divide-slate-800">{environments.map(item => <div key={item.id} className="flex flex-wrap items-center gap-3 p-3"><Boxes size={15} className="text-cyan-400" /><div className="min-w-0 flex-1"><strong className="text-xs">{item.name}</strong><p className="mb-1 mt-1 font-mono text-[10px] text-slate-500">{item.base_url || 'No base URL'}</p><div className="flex flex-wrap gap-1">{Object.keys(item.variables).map(key => <Badge key={key}>{key}</Badge>)}{Object.keys(item.secrets).map(key => <Badge key={key} tone="info">{key} · secret</Badge>)}</div></div><Button size="sm" onClick={() => editEnvironment(item)}>Edit</Button><Button size="sm" variant="danger" disabled={busy} onClick={() => void remove(item.id)}><Trash2 size={13} /> Delete</Button></div>)}</div>}
    </Panel>
  </>
}
