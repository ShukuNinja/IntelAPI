import { useState } from 'react'
import { ChevronDown, Copy, Plus, RotateCcw, Save, Send, Settings2 } from 'lucide-react'
import { PageHeader } from '../../components/ui/PageHeader'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Panel } from '../../components/ui/Panel'

const sampleBody = JSON.stringify({ "page": 1, "limit": 20 }, null, 2)
export function WorkspacePage() {
  const [method, setMethod] = useState('GET')
  const [url, setUrl] = useState('https://api.example.com/v1/users')
  const [body, setBody] = useState(sampleBody)
  const [activeTab, setActiveTab] = useState('Params')
  const [responseTab, setResponseTab] = useState('Pretty')
  const [showNotice, setShowNotice] = useState(false)
  return <>
    <PageHeader eyebrow="REQUEST BUILDER" title="API Workspace" description="Compose requests, inspect responses, and save repeatable API checks."
      actions={<><Button><Save size={15} /> Save request</Button><Button variant="primary" onClick={() => setShowNotice(true)}><Send size={15} /> Send request</Button></>} />
    {showNotice && <div className="notice notice--warning"><span className="notice__icon"><Settings2 size={16} /></span><div><strong>Execution is not connected yet</strong><p>This stage implements the request editor only. No network request was sent. The backend execution service will be connected in a later milestone.</p></div><button className="notice__close" onClick={() => setShowNotice(false)} aria-label="Dismiss">×</button></div>}
    <div className="workspace-toolbar"><div className="crumb-small"><span>Collections</span><span>/</span><strong>Users API</strong><ChevronDown size={14} /></div><div className="toolbar-actions"><Badge>Unsaved</Badge><Button size="sm"><Copy size={14} /> Copy cURL</Button><Button size="sm"><RotateCcw size={14} /> Reset</Button></div></div>
    <Panel title="Request" subtitle="Configure the HTTP request">
      <div className="request-line"><select aria-label="HTTP method" value={method} onChange={(e) => setMethod(e.target.value)}>{['GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS'].map(m => <option key={m}>{m}</option>)}</select><input aria-label="Request URL" value={url} onChange={(e) => setUrl(e.target.value)} spellCheck={false} /><Button variant="primary" onClick={() => setShowNotice(true)}><Send size={15} /> Send</Button></div>
      <div className="tab-bar">{['Params','Headers','Body','Auth','Scripts'].map(tab => <button key={tab} className={`tab-button${activeTab === tab ? ' tab-button--active' : ''}`} onClick={() => setActiveTab(tab)}>{tab}{tab === 'Headers' && <span className="tab-count">2</span>}</button>)}</div>
      {activeTab === 'Params' && <div className="key-value-table"><div className="key-value-row key-value-row--head"><span>KEY</span><span>VALUE</span><span>DESCRIPTION</span><span /></div><div className="key-value-row"><input aria-label="Parameter key" placeholder="page" /><input aria-label="Parameter value" placeholder="1" /><input aria-label="Parameter description" placeholder="Page number" /><button aria-label="Remove parameter">×</button></div><div className="key-value-row"><input aria-label="Parameter key" placeholder="limit" /><input aria-label="Parameter value" placeholder="20" /><input aria-label="Parameter description" placeholder="Page size" /><button aria-label="Remove parameter">×</button></div><button className="add-row"><Plus size={14} /> Add parameter</button></div>}
      {activeTab === 'Headers' && <div className="key-value-table"><div className="key-value-row key-value-row--head"><span>KEY</span><span>VALUE</span><span>DESCRIPTION</span><span /></div><div className="key-value-row"><input aria-label="Header key" value="Accept" readOnly /><input aria-label="Header value" value="application/json" readOnly /><input aria-label="Header description" placeholder="Response format" /><span /></div><div className="key-value-row"><input aria-label="Header key" placeholder="Authorization" /><input aria-label="Header value" placeholder="Bearer token" /><input aria-label="Header description" placeholder="Optional" /><span /></div><button className="add-row"><Plus size={14} /> Add header</button></div>}
      {activeTab === 'Body' && <div className="editor-wrap"><div className="editor-toolbar"><span>JSON</span><button type="button" onClick={() => setBody(sampleBody)}>Reset example</button></div><textarea className="code-editor" aria-label="Request body JSON" value={body} onChange={e => setBody(e.target.value)} spellCheck={false} /></div>}
      {activeTab === 'Auth' && <div className="auth-placeholder"><label htmlFor="auth-type">Authorization type</label><select id="auth-type"><option>No Auth</option><option>Bearer Token (UI placeholder)</option><option>Basic Auth (UI placeholder)</option><option>API Key (UI placeholder)</option></select><p>Credential handling will be implemented with backend-side secret protection.</p></div>}
      {activeTab === 'Scripts' && <div className="empty-inline"><Settings2 size={18} /><div><strong>Request scripts are out of MVP scope</strong><p>A sandboxed scripting runtime is not implemented in this version.</p></div></div>}
    </Panel>
    <Panel title="Response" subtitle="Response preview" className="response-panel" action={<Badge>Not executed</Badge>}>
      <div className="response-empty"><span className="response-empty__icon"><Send size={20} /></span><h3>No response yet</h3><p>Configure a request, then connect the backend execution engine to send it safely.</p></div>
      <div className="response-meta"><span>STATUS <strong>—</strong></span><span>TIME <strong>—</strong></span><span>SIZE <strong>—</strong></span></div>
      <div className="tab-bar">{['Pretty','Raw','Headers','Cookies'].map(tab => <button key={tab} className={`tab-button${responseTab === tab ? ' tab-button--active' : ''}`} onClick={() => setResponseTab(tab)}>{tab}</button>)}</div>
      <div className="response-code"><span className="line-number">1</span><span className="code-muted">{responseTab === 'Pretty' ? 'Response content will appear here.' : `No ${responseTab.toLowerCase()} captured.`}</span></div>
    </Panel>
  </>
}