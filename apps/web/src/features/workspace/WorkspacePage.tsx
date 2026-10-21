import { useEffect, useState, type Dispatch, type SetStateAction } from 'react'
import {
  ChevronDown,
  Copy,
  Plus,
  RotateCcw,
  Save,
  Send,
  Settings2,
  Trash2,
} from 'lucide-react'
import { PageHeader } from '../../components/ui/PageHeader'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Panel } from '../../components/ui/Panel'
import { ApiError } from '../../lib/apiClient'
import { apiRequest } from '../../lib/apiClient'
import { useProject } from '../projects/ProjectContext'
import { workspaceService, type ExecutionRecord, type SavedRequest } from './workspaceService'
import type { HttpMethod } from './executionService'

const sampleBody = JSON.stringify({ page: 1, limit: 20 }, null, 2)

type KeyValueRow = {
  id: number
  key: string
  value: string
  description: string
  enabled: boolean
}

const initialParams: KeyValueRow[] = [
  { id: 1, key: 'page', value: '1', description: 'Page number', enabled: true },
  { id: 2, key: 'limit', value: '20', description: 'Page size', enabled: true },
]

const initialHeaders: KeyValueRow[] = [
  {
    id: 3,
    key: 'Accept',
    value: 'application/json',
    description: 'Response format',
    enabled: true,
  },
]

function rowsToRecord(rows: KeyValueRow[]): Record<string, string> {
  const result: Record<string, string> = {}

  for (const row of rows) {
    const key = row.key.trim()
    if (row.enabled && key) result[key] = row.value
  }

  return result
}

function persistedBody(method: HttpMethod, rawBody: string, headers: Record<string, string>): { body: unknown | null; body_type: 'none' | 'json' | 'text' } {
  if (['GET', 'HEAD'].includes(method) || !rawBody.trim()) return { body: null, body_type: 'none' }
  const isJson = Object.entries(headers).some(([key, value]) => key.toLowerCase() === 'content-type' && value.toLowerCase().includes('application/json'))
  if (isJson) {
    try { return { body: JSON.parse(rawBody), body_type: 'json' } }
    catch { throw new Error('The request body is not valid JSON.') }
  }
  return { body: rawBody, body_type: 'text' }
}

function buildEffectiveUrl(
  input: string,
  queryParams: Record<string, string>,
): string {
  const trimmedInput = input.trim()

  // Accept a Markdown link such as:
  // [https://httpbin.org/get?page=2](https://httpbin.org/get?page=2)
  const markdownLink = trimmedInput.match(
    /^\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)$/,
  )

  const candidate = markdownLink
    ? markdownLink[2]
    : trimmedInput

  let parsedUrl: URL

  try {
    parsedUrl = new URL(candidate)
  } catch {
    throw new Error(
      'Enter a valid absolute URL, such as https://httpbin.org/get',
    )
  }

  if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
    throw new Error('Only HTTP and HTTPS URLs are supported.')
  }

  for (const [key, value] of Object.entries(queryParams)) {
    parsedUrl.searchParams.set(key, value)
  }

  return parsedUrl.toString()
}

function validateDuplicateKeys(
  rows: KeyValueRow[],
  label: string,
  caseInsensitive = false,
): string | null {
  const seen = new Set<string>()

  for (const row of rows) {
    if (!row.enabled) continue

    const key = row.key.trim()
    if (!key) continue

    const normalizedKey = caseInsensitive ? key.toLowerCase() : key

    if (seen.has(normalizedKey)) {
      return `Duplicate ${label} key "${key}". Each enabled ${label} key must be unique.`
    }

    seen.add(normalizedKey)
  }

  return null
}

function formatResponseBody(body: string): string {
  try {
    return JSON.stringify(JSON.parse(body), null, 2)
  } catch {
    return body
  }
}

function quoteShell(value: string): string {
  return `'${value.replace(/'/g, "'\\''")}'`
}

function buildCurl(
  method: HttpMethod,
  url: string,
  headers: Record<string, string>,
  body: string,
  queryParams: Record<string, string>,
): string {
  const effectiveUrl = buildEffectiveUrl(url, queryParams)
  const parts = [`curl -X ${quoteShell(method)}`, quoteShell(effectiveUrl)]

  for (const [key, value] of Object.entries(headers)) {
    parts.push(`-H ${quoteShell(`${key}: ${value}`)}`)
  }

  if (body && !['GET', 'HEAD'].includes(method)) {
    parts.push(`--data-raw ${quoteShell(body)}`)
  }

  return parts.join(' \\\n  ')
}

export function WorkspacePage() {
  const { project } = useProject()
  const [method, setMethod] = useState<HttpMethod>('GET')
  const [url, setUrl] = useState('https://httpbin.org/get')
  const [body, setBody] = useState(sampleBody)
  const [params, setParams] = useState(initialParams)
  const [headers, setHeaders] = useState(initialHeaders)
  const [activeTab, setActiveTab] = useState('Params')
  const [responseTab, setResponseTab] = useState('Pretty')
  const [response, setResponse] = useState<ExecutionRecord | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [nextRowId, setNextRowId] = useState(4)
  const [savedRequests, setSavedRequests] = useState<SavedRequest[]>([])
  const [selectedRequestId, setSelectedRequestId] = useState('')
  const [requestName, setRequestName] = useState('New request')
  const [environments, setEnvironments] = useState<Array<{ id: string; name: string }>>([])
  const [collections, setCollections] = useState<Array<{ id: string; name: string }>>([])
  const [collectionId, setCollectionId] = useState('')
  const [environmentId, setEnvironmentId] = useState('')
  const [loadingSaved, setLoadingSaved] = useState(false)

  useEffect(() => {
    if (!project) { setSavedRequests([]); setEnvironments([]); setCollections([]); setSelectedRequestId(''); return }
    setSelectedRequestId('')
    setLoadingSaved(true)
    Promise.all([
      workspaceService.listRequests(project.id),
      apiRequest<{ items: Array<{ id: string; name: string }> }>(`/v1/projects/${project.id}/environments`),
      apiRequest<{ items: Array<{ id: string; name: string }> }>(`/v1/projects/${project.id}/collections`),
    ]).then(([requests, envs, groups]) => {
      setSavedRequests(requests.items)
      setEnvironments(envs.items)
      setCollections(groups.items)
    }).catch((err: unknown) => setError(err instanceof Error ? err.message : 'Unable to load project requests.'))
      .finally(() => setLoadingSaved(false))
  }, [project])

  const requestHeaders = rowsToRecord(headers)
  const requestParams = rowsToRecord(params)

  function updateRow(
    rows: KeyValueRow[],
    setRows: (rows: KeyValueRow[]) => void,
    id: number,
    field: keyof KeyValueRow,
    value: string | boolean,
  ) {
    setRows(
      rows.map((row) =>
        row.id === id ? { ...row, [field]: value } : row,
      ),
    )
  }

  function addRow(
  setRows: Dispatch<SetStateAction<KeyValueRow[]>>,
) {
  setRows((current) => [
    ...current,
    {
      id: nextRowId,
      key: '',
      value: '',
      description: '',
      enabled: true,
    },
  ])

  setNextRowId((id) => id + 1)
}

  async function sendRequest() {
    setLoading(true)
    setError(null)
    setNotice(null)
    setResponse(null)

    try {
      const trimmedUrl = url.trim()

      if (!trimmedUrl) {
        throw new Error('Enter a request URL.')
      }

      const paramsError = validateDuplicateKeys(params, 'query parameter')
      if (paramsError) throw new Error(paramsError)

      const headersError = validateDuplicateKeys(headers, 'header', true)
      if (headersError) throw new Error(headersError)

      let requestBody: string | null = null

      if (!['GET', 'HEAD'].includes(method) && body.trim()) {
        // Validate JSON when the request declares a JSON content type.
        const contentType = Object.entries(requestHeaders).find(
          ([key]) => key.toLowerCase() === 'content-type',
        )?.[1]

        if (contentType?.toLowerCase().includes('application/json')) {
          try {
            JSON.parse(body)
          } catch {
            throw new Error('The request body is not valid JSON.')
          }
        }

        requestBody = body
      }

      if (!project) throw new Error('Create or select a project before executing a saved request.')
      const bodyData = persistedBody(method, requestBody ?? '', requestHeaders)
      const input = {
        name: requestName.trim() || 'Untitled request',
        method,
        url_template: trimmedUrl,
        collection_id: collectionId || null,
        environment_id: environmentId || null,
        headers: requestHeaders,
        query_params: requestParams,
        body: bodyData.body,
        body_type: bodyData.body_type,
      }
      let saved = savedRequests.find((item) => item.id === selectedRequestId)
      if (saved) saved = await workspaceService.updateRequest(saved.id, input)
      else saved = await workspaceService.saveRequest(project.id, input)
      setSelectedRequestId(saved.id)
      setSavedRequests((current) => [saved!, ...current.filter((item) => item.id !== saved!.id)])
      setResponse(await workspaceService.executeRequest(saved.id, environmentId || null))
    } catch (err) {
      if (err instanceof ApiError) {
        setError(
          `Execution request failed with HTTP ${err.status}. ` +
            (err.requestId ? `Request ID: ${err.requestId}` : '') +
            ' Check your session, request configuration, and API logs.',
        )
      } else if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('An unexpected error occurred while executing the request.')
      }
    } finally {
      setLoading(false)
    }
  }

  async function saveRequest() {
    if (!project) { setError('Create or select a project before saving a request.'); return }
    try {
      const bodyData = persistedBody(method, body, requestHeaders)
      const input = {
        name: requestName.trim() || 'Untitled request', method, url_template: url.trim(),
        collection_id: collectionId || null, environment_id: environmentId || null,
        headers: requestHeaders, query_params: requestParams,
        body: bodyData.body,
        body_type: bodyData.body_type,
      }
      const saved = selectedRequestId ? await workspaceService.updateRequest(selectedRequestId, input) : await workspaceService.saveRequest(project.id, input)
      setSelectedRequestId(saved.id)
      setSavedRequests((current) => [saved, ...current.filter((item) => item.id !== saved.id)])
      setNotice('Request saved to this project.')
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save request.') }
  }

  function openSavedRequest(id: string) {
    const saved = savedRequests.find((item) => item.id === id)
    if (!saved) { setSelectedRequestId(''); setResponse(null); return }
    setSelectedRequestId(id); setRequestName(saved.name); setMethod(saved.method); setUrl(saved.url_template)
    setEnvironmentId(saved.environment_id ?? '')
    setCollectionId(saved.collection_id ?? '')
    setBody(typeof saved.body === 'string' ? saved.body : saved.body == null ? '' : JSON.stringify(saved.body, null, 2))
    setHeaders(Object.entries(saved.headers).map(([key, value], index) => ({ id: index + 1, key, value, description: '', enabled: true })))
    setParams(Object.entries(saved.query_params).map(([key, value], index) => ({ id: index + 100, key, value, description: '', enabled: true })))
    setResponse(null); setError(null)
  }

  async function deleteSavedRequest() {
    if (!selectedRequestId) return
    try {
      await workspaceService.deleteRequest(selectedRequestId)
      setSavedRequests((current) => current.filter((item) => item.id !== selectedRequestId))
      resetRequest()
      setNotice('Saved request deleted.')
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to delete request.') }
  }

  async function copyText(value: string, label: string) {
    try {
      await navigator.clipboard.writeText(value)
      setNotice(`${label} copied to clipboard.`)
    } catch {
      setNotice('Clipboard access failed. Copy the text manually.')
    }
  }

  function resetRequest() {
    setSelectedRequestId('')
    setRequestName('New request')
    setCollectionId('')
    setEnvironmentId('')
    setMethod('GET')
    setUrl('https://httpbin.org/get')
    setBody(sampleBody)
    setParams(initialParams)
    setHeaders(initialHeaders)
    setResponse(null)
    setError(null)
    setNotice(null)
  }

  const responseText =
    response === null
      ? ''
      : responseTab === 'Headers'
        ? JSON.stringify(response.response_headers, null, 2)
        : responseTab === 'Cookies'
          ? 'Cookies are not exposed by the execution response.'
          : responseTab === 'Raw'
            ? (response.response_body ?? response.error_message ?? '')
            : formatResponseBody(response.response_body ?? response.error_message ?? '')

  return (
    <>
      <PageHeader
        eyebrow="REQUEST BUILDER"
        title="API Workspace"
        description="Compose requests, inspect responses, and save repeatable API checks."
        actions={
          <>
            <Button onClick={() => void saveRequest()} disabled={!project}>
              <Save size={15} /> Save request
            </Button>
            <Button variant="primary" onClick={sendRequest} disabled={loading}>
              <Send size={15} /> {loading ? 'Sending…' : 'Send request'}
            </Button>
          </>
        }
      />

      {notice && (
        <div className="notice">
          <span>{notice}</span>
          <button
            className="notice__close"
            onClick={() => setNotice(null)}
            aria-label="Dismiss notice"
          >
            ×
          </button>
        </div>
      )}

      <div className="workspace-toolbar">
        <div className="workspace-request-picker">
          <input aria-label="Request name" value={requestName} onChange={(event) => setRequestName(event.target.value)} />
          <select aria-label="Open saved request" value={selectedRequestId} onChange={(event) => openSavedRequest(event.target.value)}>
            <option value="">{loadingSaved ? 'Loading requests…' : 'New request'}</option>
            {savedRequests.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <select aria-label="Request collection" value={collectionId} onChange={(event) => setCollectionId(event.target.value)}>
            <option value="">No collection</option>
            {collections.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <select aria-label="Execution environment" value={environmentId} onChange={(event) => setEnvironmentId(event.target.value)}>
            <option value="">No environment</option>
            {environments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </div>
        <div className="crumb-small">
          <span>Collections</span>
          <span>/</span>
          <strong>Users API</strong>
          <ChevronDown size={14} />
        </div>
        <div className="toolbar-actions">
          <Badge>{response ? 'Executed' : 'Unsaved'}</Badge>
          {selectedRequestId && <Button size="sm" variant="danger" onClick={() => void deleteSavedRequest()} aria-label="Delete saved request"><Trash2 size={14} /> Delete</Button>}
          <Button
            size="sm"
            onClick={() =>
              copyText(
                buildCurl(method, url, requestHeaders, body, requestParams),
                'cURL command',
              )
            }
          >
            <Copy size={14} /> Copy cURL
          </Button>
          <Button size="sm" onClick={resetRequest}>
            <RotateCcw size={14} /> Reset
          </Button>
        </div>
      </div>

      <Panel title="Request" subtitle="Configure the HTTP request">
        <div className="request-line">
          <select
            aria-label="HTTP method"
            value={method}
            onChange={(event) => setMethod(event.target.value as HttpMethod)}
          >
            {['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'].map(
              (value) => (
                <option key={value}>{value}</option>
              ),
            )}
          </select>
          <input
            aria-label="Request URL"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            spellCheck={false}
            placeholder="https://api.example.com/endpoint"
          />
          <Button variant="primary" onClick={sendRequest} disabled={loading}>
            <Send size={15} /> {loading ? 'Sending…' : 'Send'}
          </Button>
        </div>

        <div className="tab-bar">
          {['Params', 'Headers', 'Body', 'Auth', 'Scripts'].map((tab) => (
            <button
              key={tab}
              className={`tab-button${activeTab === tab ? ' tab-button--active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
              {tab === 'Headers' && (
                <span className="tab-count">{headers.filter((h) => h.enabled).length}</span>
              )}
            </button>
          ))}
        </div>

        {activeTab === 'Params' && (
          <div className="key-value-table">
            <div className="key-value-row key-value-row--head">
              <span>KEY</span><span>VALUE</span><span>DESCRIPTION</span><span />
            </div>
            {params.map((row) => (
              <div className="key-value-row" key={row.id}>
                <input
                  type="checkbox"
                  aria-label={`Enable parameter ${row.key || row.id}`}
                  checked={row.enabled}
                  onChange={(event) =>
                    updateRow(params, setParams, row.id, 'enabled', event.target.checked)
                  }
                />
                <input
                  aria-label="Parameter key"
                  placeholder="page"
                  value={row.key}
                  onChange={(event) =>
                    updateRow(params, setParams, row.id, 'key', event.target.value)
                  }
                />
                <input
                  aria-label="Parameter value"
                  placeholder="1"
                  value={row.value}
                  onChange={(event) =>
                    updateRow(params, setParams, row.id, 'value', event.target.value)
                  }
                />
                <input
                  aria-label="Parameter description"
                  placeholder="Description"
                  value={row.description}
                  onChange={(event) =>
                    updateRow(params, setParams, row.id, 'description', event.target.value)
                  }
                />
                <button
                  aria-label="Remove parameter"
                  onClick={() => setParams((current) => current.filter((item) => item.id !== row.id))}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
            <button className="add-row" onClick={() => addRow(setParams)}>
              <Plus size={14} /> Add parameter
            </button>
          </div>
        )}

        {activeTab === 'Headers' && (
          <div className="key-value-table">
            <div className="key-value-row key-value-row--head">
              <span>ON</span><span>KEY</span><span>VALUE</span><span>DESCRIPTION</span><span />
            </div>
            {headers.map((row) => (
              <div className="key-value-row" key={row.id}>
                <input
                  type="checkbox"
                  aria-label={`Enable header ${row.key || row.id}`}
                  checked={row.enabled}
                  onChange={(event) =>
                    updateRow(headers, setHeaders, row.id, 'enabled', event.target.checked)
                  }
                />
                <input
                  aria-label="Header key"
                  placeholder="Authorization"
                  value={row.key}
                  onChange={(event) =>
                    updateRow(headers, setHeaders, row.id, 'key', event.target.value)
                  }
                />
                <input
                  aria-label="Header value"
                  placeholder="Bearer token"
                  value={row.value}
                  onChange={(event) =>
                    updateRow(headers, setHeaders, row.id, 'value', event.target.value)
                  }
                />
                <input
                  aria-label="Header description"
                  placeholder="Description"
                  value={row.description}
                  onChange={(event) =>
                    updateRow(headers, setHeaders, row.id, 'description', event.target.value)
                  }
                />
                <button
                  aria-label="Remove header"
                  onClick={() => setHeaders((current) => current.filter((item) => item.id !== row.id))}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
            <button className="add-row" onClick={() => addRow(setHeaders)}>
              <Plus size={14} /> Add header
            </button>
          </div>
        )}

        {activeTab === 'Body' && (
          <div className="editor-wrap">
            <div className="editor-toolbar">
              <span>JSON / raw</span>
              <button type="button" onClick={() => setBody(sampleBody)}>
                Reset example
              </button>
            </div>
            <textarea
              className="code-editor"
              aria-label="Request body"
              value={body}
              onChange={(event) => setBody(event.target.value)}
              spellCheck={false}
            />
          </div>
        )}

        {activeTab === 'Auth' && (
          <div className="auth-placeholder">
            <label htmlFor="auth-type">Authorization</label>
            <p>
              Add an Authorization header under Headers. For reusable secrets,
              store the value in an encrypted secret variable on an environment.
            </p>
          </div>
        )}

        {activeTab === 'Scripts' && (
          <div className="empty-inline">
            <Settings2 size={18} />
            <div>
              <strong>Request scripts are out of MVP scope</strong>
              <p>A sandboxed scripting runtime is not implemented in this version.</p>
            </div>
          </div>
        )}
      </Panel>

      <Panel
        title="Response"
        subtitle="Actual response from the target API"
        className="response-panel"
        action={
          <Badge>
            {loading
              ? 'Executing'
              : response
                ? `${response.response_status_code ?? response.status} ${response.status === 'completed' ? 'Completed' : 'Failed'}`
                : error
                  ? 'Failed'
                  : 'Not executed'}
          </Badge>
        }
      >
        {loading && (
          <div className="response-empty">
            <h3>Executing request…</h3>
            <p>Waiting for the execution service to return a response.</p>
          </div>
        )}

        {error && (
          <div className="notice notice--warning" role="alert">
            <strong>Request failed</strong>
            <p>{error}</p>
          </div>
        )}

        {!loading && !response && !error && (
          <div className="response-empty">
            <span className="response-empty__icon"><Send size={20} /></span>
            <h3>No response yet</h3>
            <p>Configure your request and select Send to execute it.</p>
          </div>
        )}

        {response && (
          <>
            <div className="response-meta">
              <span>STATUS <strong>{response.response_status_code ?? response.status}</strong></span>
              <span>TIME <strong>{response.duration_ms ?? 0} ms</strong></span>
              <span>EXECUTION <strong>{response.id.slice(0, 8)}</strong></span>
            </div>
            <div className="response-meta">
              <span>REQUEST URL <strong>{response.url}</strong></span>
            </div>
            <div className="tab-bar">
              {['Pretty', 'Raw', 'Headers', 'Cookies'].map((tab) => (
                <button
                  key={tab}
                  className={`tab-button${responseTab === tab ? ' tab-button--active' : ''}`}
                  onClick={() => setResponseTab(tab)}
                >
                  {tab}
                </button>
              ))}
              <Button
                size="sm"
                onClick={() => copyText(responseText, 'Response')}
              >
                <Copy size={14} /> Copy response
              </Button>
            </div>
            <pre className="response-code" style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
              {responseText || '(empty response body)'}
            </pre>
          </>
        )}
      </Panel>
    </>
  )
}
