import { useCallback, useEffect, useMemo, useState } from 'react'
import { FileSearch2, FileUp, Search, UploadCloud, WandSparkles } from 'lucide-react'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { MethodBadge } from '../../components/ui/MethodBadge'
import { EmptyState } from '../../components/ui/EmptyState'
import { useProject } from '../projects/ProjectContext'
import { specificationService, type ApiOperation, type CandidatePreview, type KnowledgeFact, type Specification } from './specificationService'

export function ExplorerPage() {
  const { project } = useProject()
  const [specs, setSpecs] = useState<Specification[]>([])
  const [selected, setSelected] = useState('')
  const [operations, setOperations] = useState<ApiOperation[]>([])
  const [filter, setFilter] = useState('')
  const [fileContent, setFileContent] = useState('')
  const [url, setUrl] = useState('')
  const [preview, setPreview] = useState<{ operationId: string; result: CandidatePreview } | null>(null)
  const [detail, setDetail] = useState<{ operation: ApiOperation; facts: KnowledgeFact[] } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!project) { setSpecs([]); setSelected(''); setOperations([]); return }
    try {
      const result = await specificationService.list(project.id)
      setSpecs(result.items)
      setSelected(current => result.items.some(item => item.id === current) ? current : (result.items[0]?.id ?? ''))
      setError(null)
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to load API specifications.') }
  }, [project])

  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    if (!selected) { setOperations([]); return }
    void specificationService.operations(selected).then(result => setOperations(result.items)).catch(err => setError(err instanceof Error ? err.message : 'Unable to load operations.'))
  }, [selected])

  const visible = useMemo(() => operations.filter(op => `${op.method} ${op.path_template} ${op.summary ?? ''}`.toLowerCase().includes(filter.toLowerCase())), [operations, filter])
  const currentSpec = specs.find(item => item.id === selected)

  async function importSpec() {
    if (!project || (!fileContent.trim() && !url.trim())) return
    setBusy(true); setError(null)
    try {
      const result = await specificationService.import(project.id, url.trim() ? { url: url.trim() } : { content: fileContent })
      setFileContent(''); setUrl('')
      await refresh()
      setSelected(result.id)
    } catch (err) { setError(err instanceof Error ? err.message : 'Specification import failed.') }
    finally { setBusy(false) }
  }

  async function loadFile(file?: File) {
    if (!file) return
    if (file.size > 2_200_000) { setError('OpenAPI documents must be no larger than 2.2 MB.'); return }
    setFileContent(await file.text())
    setUrl('')
    setError(null)
  }

  async function showCandidates(operation: ApiOperation) {
    setBusy(true); setError(null)
    try { setPreview({ operationId: operation.id, result: await specificationService.preview(operation.id) }) }
    catch (err) { setError(err instanceof Error ? err.message : 'Candidate preview failed.') }
    finally { setBusy(false) }
  }

  async function showDetails(operation: ApiOperation) {
    setBusy(true); setError(null)
    try { setDetail({ operation, facts: await specificationService.facts(operation.id) }) }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to load operation details.') }
    finally { setBusy(false) }
  }

  return <>
    <PageHeader eyebrow="API UNDERSTANDING" title="API Explorer" description="Import a contract, browse normalized operations, and preview generated tests." />
    {!project && <div className="notice notice--warning">Choose or create a project before importing an API specification.</div>}
    {error && <div className="notice notice--warning"><span className="notice__icon"><FileUp size={16} /></span><div><strong>Request failed</strong><p>{error}</p></div><button className="notice__close" onClick={() => setError(null)} aria-label="Dismiss">×</button></div>}
    <Panel title="Import OpenAPI" subtitle="Upload JSON or YAML, or provide a public HTTP(S) document URL.">
      <div className="resource-form">
        <label className="button button--secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}><UploadCloud size={15} /> Choose file<input aria-label="OpenAPI file" type="file" accept=".json,.yaml,.yml,application/json,text/yaml" hidden onChange={event => void loadFile(event.target.files?.[0])} /></label>
        <input aria-label="OpenAPI URL" value={url} onChange={event => { setUrl(event.target.value); setFileContent('') }} placeholder="https://api.example.com/openapi.json" />
        <Button variant="primary" disabled={!project || busy || (!fileContent.trim() && !url.trim())} onClick={() => void importSpec()}><FileUp size={15} /> {busy ? 'Working…' : 'Import specification'}</Button>
      </div>
      {fileContent && <small className="muted-cell">Document loaded ({new Blob([fileContent]).size.toLocaleString()} bytes). It will be validated before saving.</small>}
    </Panel>
    {specs.length > 0 && <div className="resource-form"><label htmlFor="spec-select">Specification</label><select id="spec-select" value={selected} onChange={event => { setSelected(event.target.value); setPreview(null) }}>{specs.map(spec => <option key={spec.id} value={spec.id}>{spec.name} · {spec.operation_count} operations · {new Date(spec.created_at).toLocaleDateString()}</option>)}</select></div>}
    {currentSpec && <div className="explorer-summary"><div className="explorer-summary__icon"><FileSearch2 size={21} /></div><div><strong>{currentSpec.name}</strong><p>OpenAPI {currentSpec.openapi_version ?? 'document'} <span>·</span> {currentSpec.source_kind === 'url' ? currentSpec.source_url : 'Uploaded document'}</p></div><div className="explorer-summary__stats"><span><strong>{currentSpec.operation_count}</strong> operations</span><Badge tone="info">Persisted</Badge></div></div>}
    <Panel title="Operations" subtitle={currentSpec ? `${visible.length} matching operations` : 'Import a specification to browse its operations.'} action={currentSpec ? <div className="search-field"><Search size={15} /><input value={filter} onChange={event => setFilter(event.target.value)} placeholder="Filter endpoints…" aria-label="Filter endpoints" /></div> : undefined}>
      {!currentSpec ? <EmptyState title="No specifications yet" description="Import an OpenAPI 3.0 or 3.1 document to get started." /> : <div className="table-wrap"><table><thead><tr><th>METHOD</th><th>PATH</th><th>SUMMARY</th><th>ACTION</th></tr></thead><tbody>{visible.map(operation => <tr key={operation.id}><td><MethodBadge method={operation.method} /></td><td><code className="path-code">{operation.path_template}</code></td><td>{operation.summary || '—'}</td><td><Button size="sm" disabled={busy} onClick={() => void showDetails(operation)}>Details</Button> <Button size="sm" disabled={busy} onClick={() => void showCandidates(operation)}><WandSparkles size={14} /> Preview tests</Button></td></tr>)}</tbody></table>{visible.length === 0 && <div className="table-empty">No operations match “{filter}”.</div>}</div>}
    </Panel>
    {detail && <Panel title={`Operation details · ${detail.operation.method.toUpperCase()} ${detail.operation.path_template}`} subtitle={detail.operation.summary || detail.operation.operation_key} action={<Button size="sm" onClick={() => setDetail(null)}>Close</Button>}>
      <div className="metrics-grid metrics-grid--three">
        <div><strong>Parameters</strong><pre className="code-preview">{JSON.stringify(detail.operation.operation_document.parameters, null, 2)}</pre></div>
        <div><strong>Request body schema</strong><pre className="code-preview">{JSON.stringify(detail.operation.operation_document.request_body_schema, null, 2)}</pre></div>
        <div><strong>Response schemas</strong><pre className="code-preview">{JSON.stringify(detail.operation.operation_document.response_schemas, null, 2)}</pre></div>
      </div>
      <p className="muted-cell">Source: {String((detail.operation.operation_document.source_ref as Record<string, unknown> | undefined)?.pointer ?? 'not recorded')}</p>
      <strong>Extracted knowledge facts ({detail.facts.length})</strong>
      {detail.facts.length ? <div className="resource-list">{detail.facts.map(fact => <article className="environment-card" key={fact.id}><div className="environment-card__body"><strong>{fact.subject}</strong><small>{fact.fact_type} · {fact.provenance} · confidence {fact.confidence ?? '—'}</small><pre className="code-preview">{JSON.stringify(fact.fact_value, null, 2)}</pre></div></article>)}</div> : <p className="muted-cell">No knowledge facts were extracted for this operation.</p>}
    </Panel>}
    {preview && <Panel title="Generated test candidates" subtitle={`Preview only · LLM ${preview.result.llm_status}`}><div className="resource-list">{preview.result.items.map(item => <article className="environment-card" key={item.candidate_id}><div className="environment-card__body"><strong>{item.title}</strong><p><Badge>{item.category}</Badge> <code>{item.method} {item.path}</code></p><small>{item.rationale}</small></div></article>)}{preview.result.items.length === 0 && <EmptyState title="No candidates generated" description="This operation may not expose enough contract detail for the deterministic generator." />}{preview.result.llm_error && <small>{preview.result.llm_error}</small>}</div></Panel>}
    <div className="notice notice--info"><span className="notice__icon"><FileSearch2 size={16} /></span><div><strong>Provenance preserved</strong><p>Imported contracts and extracted facts are stored with their source; candidate previews do not create executions or durable tests.</p></div></div>
  </>
}
