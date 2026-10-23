import { useMemo, useState } from 'react'
import { FileSearch2, Search, UploadCloud } from 'lucide-react'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { MethodBadge } from '../../components/ui/MethodBadge'
import { apiRequest } from '../../lib/apiClient'

type Operation = { id: string; method: string; path: string; summary: string; description: string; tags: string[]; parameters: unknown[]; request_body: Record<string, unknown> }
type ParsedSpec = { specification: { title: string; version: string }; operations: Operation[] }
type Candidate = { id: string; kind: string; reason: string; mutation: Record<string, unknown>; validation_status: string }
type GenerationReport = { policy_version: string; summary: { operation_count: number; candidate_count: number; endpoints_with_candidates: number; truncated: boolean }; endpoints: { operation: Operation; candidate_count: number; candidates: Candidate[] }[] }

export function ExplorerPage() {
  const [source, setSource] = useState('')
  const [sourceFormat, setSourceFormat] = useState<'json' | 'yaml'>('json')
  const [filter, setFilter] = useState('')
  const [parsed, setParsed] = useState<ParsedSpec | null>(null)
  const [selected, setSelected] = useState<Operation | null>(null)
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [report, setReport] = useState<GenerationReport | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const visible = useMemo(() => parsed?.operations.filter(op => `${op.method} ${op.path} ${op.summary} ${op.tags.join(' ')}`.toLowerCase().includes(filter.toLowerCase())) ?? [], [parsed, filter])

  async function parse(text = source, format = sourceFormat) {
    setBusy(true); setError(''); setCandidates([]); setReport(null)
    try {
      const result = await apiRequest<ParsedSpec>('/v1/specifications/parse', { method: 'POST', body: JSON.stringify({ content: text, source_format: format }) })
      setParsed(result); setSelected(null)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to parse this specification.') }
    finally { setBusy(false) }
  }

  async function preview(operation: Operation) {
    setSelected(operation); setError('')
    try {
      const result = await apiRequest<{ candidates: Candidate[] }>('/v1/specifications/candidates/preview', { method: 'POST', body: JSON.stringify({ operation }) })
      setCandidates(result.candidates)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to preview candidates.') }
  }

  async function generateReport() {
    if (!parsed || parsed.operations.length > 100) {
      setError('Generation reports support up to 100 operations at a time.')
      return
    }
    setError('')
    try {
      const result = await apiRequest<GenerationReport>('/v1/specifications/candidates/report', { method: 'POST', body: JSON.stringify({ operations: parsed.operations }) })
      setReport(result)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to generate the report.') }
  }

  return <>
    <PageHeader eyebrow="API UNDERSTANDING" title="API Explorer" description="Import an OpenAPI or Swagger document and inspect normalized operations and deterministic candidate ideas." />
    <Panel title="Import API specification" subtitle="Accepts OpenAPI 3.0/3.1 JSON or YAML and Swagger 2.0 JSON or YAML. Processing runs through the configured IntelAPI backend.">
      <div className="p-4">
        <div className="mb-2 flex items-center gap-3"><label className="text-xs text-slate-300" htmlFor="openapi-content">Specification content</label><select aria-label="Specification format" className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200" value={sourceFormat} onChange={event => setSourceFormat(event.target.value as 'json' | 'yaml')}><option value="json">JSON</option><option value="yaml">YAML</option></select></div>
        <textarea id="openapi-content" className="min-h-44 w-full rounded-lg border border-slate-700 bg-slate-950 p-3 font-mono text-xs text-slate-200" value={source} onChange={event => setSource(event.target.value)} placeholder="Paste an OpenAPI or Swagger document here…" />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button variant="primary" onClick={() => void parse()} disabled={busy || !source.trim()}><UploadCloud size={15} />{busy ? 'Parsing…' : 'Parse specification'}</Button>
          <label className="cursor-pointer text-xs text-indigo-300 hover:text-indigo-200">Choose spec file<input className="sr-only" type="file" accept="application/json,.json,application/yaml,text/yaml,.yaml,.yml" onChange={event => { const file = event.target.files?.[0]; if (file) { const format = /\.ya?ml$/i.test(file.name) ? 'yaml' : 'json'; void file.text().then(text => { setSource(text); setSourceFormat(format); void parse(text, format) }) } }} /></label>
          {parsed && <Badge tone="info">{parsed.specification.version}</Badge>}
        </div>
        {error && <p role="alert" className="mt-3 text-xs text-rose-300">{error}</p>}
      </div>
    </Panel>
    {parsed ? <>
      <div className="explorer-summary mt-4"><div className="explorer-summary__icon"><FileSearch2 size={21} /></div><div><strong>{parsed.specification.title}</strong><p>Parsed from supplied document · {parsed.specification.version}</p></div><div className="explorer-summary__stats"><span><strong>{parsed.operations.length}</strong> operations</span><Badge tone="info">Current session</Badge></div></div>
      <div className="my-3 flex justify-end"><Button variant="primary" disabled={parsed.operations.length === 0 || parsed.operations.length > 100} onClick={() => void generateReport()}><FileSearch2 size={15} />Generate candidates report</Button></div>
      <Panel title="Operations" subtitle="Parsed from this document in the current session; not saved to the database." action={<div className="search-field"><Search size={15} /><input value={filter} onChange={event => setFilter(event.target.value)} placeholder="Filter operations…" aria-label="Filter operations" /></div>}>
        <div className="table-wrap"><table><thead><tr><th>METHOD</th><th>PATH</th><th>SUMMARY</th><th>TAGS</th><th /></tr></thead><tbody>{visible.map(operation => <tr key={operation.id}><td><MethodBadge method={operation.method} /></td><td><code className="path-code">{operation.path}</code></td><td>{operation.summary || operation.description}</td><td className="muted-cell">{operation.tags.join(', ')}</td><td><Button variant="secondary" onClick={() => void preview(operation)}>Preview tests</Button></td></tr>)}</tbody></table>{visible.length === 0 && <div className="table-empty">No operations match this filter.</div>}</div>
      </Panel>
      {report && <Panel title={`Generation report · ${report.policy_version}`} subtitle={`${report.summary.candidate_count} actual candidates across ${report.summary.endpoints_with_candidates} of ${report.summary.operation_count} endpoints. Preview is session-only.`}>
        {report.summary.truncated && <p role="status" className="px-4 pt-3 text-xs text-amber-300">Report reached its configured cap. Import fewer operations to preview the remainder.</p>}
        <div className="divide-y divide-slate-800">{report.endpoints.map(endpoint => <div key={endpoint.operation.id} className="p-4"><div className="mb-2 flex flex-wrap items-center gap-2"><MethodBadge method={endpoint.operation.method} /><code className="path-code">{endpoint.operation.path}</code><Badge tone="info">{endpoint.candidate_count} candidates</Badge></div>{endpoint.candidates.map(candidate => <div key={candidate.id} className="ml-3 border-l border-slate-700 py-2 pl-3"><p className="m-0 text-xs text-slate-200">{candidate.reason}</p><code className="mt-1 block break-all text-[11px] text-slate-500">{JSON.stringify(candidate.mutation)}</code></div>)}{endpoint.candidate_count === 0 && <p className="m-0 text-xs text-slate-500">No supported candidates from the declared schema.</p>}</div>)}</div>
      </Panel>}
      {selected && <Panel title={`Candidate preview · ${selected.method} ${selected.path}`} subtitle="Deterministic suggestions derived from declared parameters and request-body constraints.">
        {candidates.length ? <div className="divide-y divide-slate-800">{candidates.map(candidate => <div key={candidate.id} className="flex flex-col gap-2 p-4 sm:flex-row sm:items-start"><Badge tone="info">{candidate.kind}</Badge><div className="min-w-0 flex-1"><p className="m-0 text-xs text-slate-200">{candidate.reason}</p><code className="mt-1 block break-all text-[11px] text-slate-400">{JSON.stringify(candidate.mutation)}</code></div><span className="text-[10px] text-slate-500">{candidate.validation_status}</span></div>)}</div> : <div className="p-5 text-xs text-slate-400">No supported schema boundary candidates were found for this operation.</div>}
      </Panel>}
    </> : <div className="mt-4"><Panel title="No specification loaded" subtitle="Paste or select an OpenAPI JSON document to view its actual operations."><div className="p-5 text-xs text-slate-400">No document has been parsed in this session.</div></Panel></div>}
  </>
}
