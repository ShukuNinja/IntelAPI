import { useState } from 'react'
import { FileSearch2, FileUp, Search, UploadCloud } from 'lucide-react'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { MethodBadge } from '../../components/ui/MethodBadge'

const endpoints = [
  { method: 'GET', path: '/v1/users', description: 'List users', group: 'Users', status: 'Documented' },
  { method: 'POST', path: '/v1/users', description: 'Create user', group: 'Users', status: 'Documented' },
  { method: 'GET', path: '/v1/users/{id}', description: 'Get user by ID', group: 'Users', status: 'Documented' },
  { method: 'PATCH', path: '/v1/users/{id}', description: 'Update user', group: 'Users', status: 'Documented' },
  { method: 'GET', path: '/v1/orders', description: 'List orders', group: 'Orders', status: 'Documented' },
  { method: 'GET', path: '/v1/orders/{id}', description: 'Get order details', group: 'Orders', status: 'Observed' },
  { method: 'POST', path: '/v1/orders', description: 'Create order', group: 'Orders', status: 'Documented' },
]
export function ExplorerPage() {
  const [filter, setFilter] = useState('')
  const [importNotice, setImportNotice] = useState(false)
  const visible = endpoints.filter(e => `${e.method} ${e.path} ${e.description} ${e.group}`.toLowerCase().includes(filter.toLowerCase()))
  return <>
    <PageHeader eyebrow="API UNDERSTANDING" title="API Explorer" description="Browse API operations, schemas, and the distinction between declared and observed behavior." actions={<Button variant="primary" onClick={() => setImportNotice(true)}><UploadCloud size={15} /> Import OpenAPI</Button>} />
    {importNotice && <div className="notice notice--warning"><span className="notice__icon"><FileUp size={16} /></span><div><strong>OpenAPI import is not connected</strong><p>Import validation and backend persistence will be added in a later milestone. No file has been uploaded.</p></div><button className="notice__close" onClick={() => setImportNotice(false)} aria-label="Dismiss">×</button></div>}
    <div className="explorer-summary"><div className="explorer-summary__icon"><FileSearch2 size={21} /></div><div><strong>Acme Public API</strong><p>Example OpenAPI document <span>·</span> v1.2.0</p></div><div className="explorer-summary__stats"><span><strong>7</strong> operations</span><span><strong>2</strong> resource groups</span><Badge tone="info">Demo spec</Badge></div></div>
    <Panel title="Operations" subtitle="Demo specification — not loaded from a live API" action={<div className="search-field"><Search size={15} /><input value={filter} onChange={e => setFilter(e.target.value)} placeholder="Filter endpoints..." aria-label="Filter endpoints" /></div>}>
      <div className="table-wrap"><table><thead><tr><th>METHOD</th><th>PATH</th><th>DESCRIPTION</th><th>GROUP</th><th>PROVENANCE</th></tr></thead><tbody>{visible.map((e, i) => <tr key={`${e.method}-${e.path}-${i}`}><td><MethodBadge method={e.method} /></td><td><code className="path-code">{e.path}</code></td><td>{e.description}</td><td className="muted-cell">{e.group}</td><td><Badge tone={e.status === 'Observed' ? 'warning' : 'info'}>{e.status}</Badge></td></tr>)}</tbody></table>{visible.length === 0 && <div className="table-empty">No operations match “{filter}”.</div>}</div>
    </Panel>
    <div className="notice notice--info"><span className="notice__icon"><FileSearch2 size={16} /></span><div><strong>Keep provenance explicit</strong><p>Imported contract details, deterministic schema extraction, inferred hypotheses, and execution observations must remain distinguishable in the implemented explorer.</p></div></div>
  </>
}