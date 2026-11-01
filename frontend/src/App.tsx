import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { createIncident, getIncident, getIncidents, Incident, NewIncident } from './api'

const defaultAlert: NewIncident = {
  serviceName: 'payment-service', environment: 'production', alertType: 'HIGH_CPU',
  cpuUtilization: 94, threshold: 80, severity: 'CRITICAL',
  description: 'CPU utilization exceeded 80% for 10 minutes',
}
const time = (value?: string) => value ? new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—'

export default function App() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [detail, setDetail] = useState<Incident | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(defaultAlert)
  const [apiHealth, setApiHealth] = useState<'checking' | 'online' | 'offline'>('checking')

  const refresh = useCallback(async (preferredId?: string) => {
    setLoading(true)
    try {
      const data = await getIncidents()
      setIncidents(data)
      const nextId = preferredId || selectedId || data[0]?.incidentId || ''
      setSelectedId(nextId)
      if (nextId) setDetail(await getIncident(nextId))
      else setDetail(null)
      setApiHealth('online')
      setMessage('')
    } catch {
      setApiHealth('offline')
      setMessage('Could not reach the NEXUS API. Check that the services are running.')
    } finally { setLoading(false) }
  }, [selectedId])

  useEffect(() => { void refresh() }, []) // initial load
  const counts = useMemo(() => ({
    total: incidents.length,
    critical: incidents.filter(i => i.severity === 'CRITICAL').length,
    investigating: incidents.filter(i => i.status === 'INVESTIGATING').length,
    completed: incidents.filter(i => i.status === 'COMPLETED').length,
  }), [incidents])

  const selectIncident = async (id: string) => {
    setSelectedId(id)
    try { setDetail(await getIncident(id)); setMessage('') }
    catch { setMessage(`Unable to load ${id}.`) }
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitting(true); setMessage('Investigation is running…')
    try {
      const created = await createIncident(form)
      setShowForm(false)
      await refresh(created.incidentId)
      setMessage(created.status === 'COMPLETED' ? `Investigation complete for ${created.incidentId}.` : `Investigation finished with status ${created.status}.`)
    } catch (error) {
      const response = (error as { response?: { data?: { message?: string; detail?: string } } }).response?.data
      setMessage(response?.message || response?.detail || 'Incident could not be created. Please check the API and try again.')
    } finally { setSubmitting(false) }
  }

  const report = detail?.investigation
  const reportErrors = report?.errors || []
  const telemetryMode = report?.telemetryMode
  const telemetryWindow = report?.telemetryWindow || {}
  const mcpToolTrace = report?.mcpToolTrace || []
  const mcpToolCatalog = report?.mcpToolCatalog || []
  const telemetryEvidence = report?.telemetryEvidence || {}

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">N</div><div><b>NEXUS<span>AI</span></b><small>INFRASTRUCTURE OPS</small></div></div>
      <div className="workspace-label">WORKSPACE</div>
      <button className="nav-item active"><span className="nav-icon">◈</span>Overview <span className="nav-count">{incidents.length}</span></button>
      <button className="nav-item" onClick={() => setShowForm(true)}><span className="nav-icon">＋</span>New investigation</button>
      <div className="side-rule" />
      <div className="workspace-label">SYSTEM</div>
      <div className="system-status"><i className={apiHealth === 'online' ? 'dot green' : apiHealth === 'offline' ? 'dot red' : 'dot'} />API {apiHealth === 'online' ? 'Operational' : apiHealth === 'offline' ? 'Unavailable' : 'Connecting'}</div>
      <div className="system-status"><i className="dot green" />LLM provider <span className="mode-pill">{report?.llmProvider?.toUpperCase() || '—'}</span></div>
      <div className="sidebar-bottom"><div className="user-avatar">NO</div><div><b>Nexus Operator</b><small>Platform engineering</small></div><span className="more">···</span></div>
    </aside>

    <main className="main-area">
      <header className="topbar"><div className="crumb">Operations <span>/</span> Incident overview</div><div className="top-actions"><span className="env-chip"><i className="dot green"/> Read-only observability</span><span className="top-date">{new Date().toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' })}</span><button className="icon-button" aria-label="Refresh" onClick={() => void refresh()}>⟳</button><div className="user-avatar mini">NO</div></div></header>
      <div className="page-content">
        <section className="page-heading"><div><div className="eyebrow">PLATFORM HEALTH <span className="live-indicator"><i/> LIVE</span></div><h1>Incident overview</h1><p>Monitor alerts and review AI-assisted infrastructure investigations.</p></div><button className="primary-button" onClick={() => setShowForm(true)}><span>＋</span> Investigate alert</button></section>

        {message && <div className={`notice ${message.startsWith('Could not') || message.includes('could not') || message.includes('Unable') ? 'notice-error' : ''}`} role="status">{message}<button onClick={() => setMessage('')} aria-label="Dismiss">×</button></div>}

        <section className="stats-grid">
          <StatCard label="Total incidents" value={counts.total} note="All recorded incidents" icon="▤" tone="blue" />
          <StatCard label="Critical incidents" value={counts.critical} note="Require immediate attention" icon="⚠" tone="red" />
          <StatCard label="Investigating" value={counts.investigating} note="Agent workflow in progress" icon="◷" tone="amber" />
          <StatCard label="Completed investigations" value={counts.completed} note="Reports ready to review" icon="✓" tone="green" />
        </section>

        <section className="content-grid">
          <div className="panel incidents-panel">
            <div className="panel-header"><div><h2>Recent incidents</h2><p>Alert intake and investigation status</p></div><button className="text-button" onClick={() => void refresh()}>Refresh ↻</button></div>
            <div className="table-wrap"><table><thead><tr><th>INCIDENT</th><th>SERVICE</th><th>ENVIRONMENT</th><th>SEVERITY</th><th>STATUS</th><th>CREATED</th></tr></thead>
              <tbody>{loading && incidents.length === 0 ? <tr><td colSpan={6} className="empty">Loading incident data…</td></tr> : incidents.length === 0 ? <tr><td colSpan={6} className="empty">No incidents yet. Submit an alert to start an investigation.</td></tr> : incidents.map(incident => <tr key={incident.incidentId} className={selectedId === incident.incidentId ? 'selected-row' : ''} onClick={() => void selectIncident(incident.incidentId)}>
                <td><button className="incident-link">{incident.incidentId}</button></td><td><b>{incident.serviceName}</b></td><td><span className="tag">{incident.environment}</span></td><td><Severity value={incident.severity}/></td><td><Status value={incident.status}/></td><td className="muted-cell">{time(incident.createdAt)}</td>
              </tr>)}</tbody></table></div>
            <div className="table-footer">Showing {incidents.length} incident{incidents.length === 1 ? '' : 's'} <span>Data refreshes on demand</span></div>
          </div>
          <div className="panel selected-card">
            <div className="panel-header"><div><h2>Selected incident</h2><p>{detail?.incidentId || 'Choose an incident to inspect'}</p></div>{detail && <Status value={detail.status}/>}</div>
            {detail ? <><div className="selected-summary"><div className="service-avatar">{detail.serviceName.split('-').map(x => x[0]).join('').slice(0,2).toUpperCase()}</div><div><h3>{detail.serviceName}</h3><span>{detail.environment} environment · {detail.alertType}</span></div></div><div className="alert-box"><div className="alert-box-head"><span>ORIGINAL ALERT</span><Severity value={detail.severity}/></div><p>{detail.description}</p><small>Received {time(detail.createdAt)}</small></div><div className="detail-meta"><div><small>INVESTIGATION</small><b>{report ? report.executionStatus : detail.status}</b></div><div><small>LLM PROVIDER</small><b>{report?.llmProvider || '—'}</b></div><div><small>TELEMETRY MODE</small><b>{telemetryMode || 'not recorded'}</b></div></div></> : <div className="empty selected-empty">Incident context and report details appear here.</div>}
          </div>
        </section>

        {detail && <section className="report-section">
          <div className="report-title"><div><div className="eyebrow">INVESTIGATION REPORT</div><h2>Evidence &amp; analysis</h2></div>{report && <div className="report-badges">{telemetryMode ? <span className={`model-badge telemetry-${telemetryMode}`}><span className="spark">◉</span> {telemetryMode === 'real' ? 'REAL PROMETHEUS / LOKI TELEMETRY' : 'MOCK FIXTURE TELEMETRY'}</span> : <span className="model-badge">TELEMETRY MODE NOT RECORDED</span>}<span className="model-badge"><span className="spark">✦</span> {report.llmProvider === 'mock' ? 'DETERMINISTIC LLM MODE' : `${report.llmProvider.toUpperCase()} MODEL`}</span></div>}</div>
          {report ? <div className="report-grid">
            <div className="panel timeline-panel"><div className="panel-header"><div><h2>Agent execution</h2><p>LangGraph workflow trace</p></div><span className="step-count">{report.executionTrace.length} / 4 steps</span></div><div className="timeline">{report.executionTrace.map((step, index) => <div className="timeline-item" key={`${step.agentName}-${index}`}><div className={`timeline-icon ${step.status === 'COMPLETED' ? 'done' : 'failed'}`}>{step.status === 'COMPLETED' ? '✓' : '!'}</div><div className="timeline-copy"><div className="timeline-heading"><b>{step.agentName}</b><span>{step.status}</span></div><p>{step.summary}</p><small>{time(step.completedAt)}</small></div></div>)}</div></div>
            <div className="panel cause-panel"><div className="panel-header"><div><h2>Probable root cause</h2><p>Correlated from {telemetryMode === 'real' ? 'Prometheus and Loki evidence' : telemetryMode === 'mock' ? 'mock fixture output' : 'evidence from this saved report'}</p></div><div className="confidence"><b>{Math.round(report.confidenceScore * 100)}%</b><small>evidence coverage</small></div></div><div className="cause-callout"><span className="cause-icon">⌁</span><p>{report.probableRootCause || 'Root cause is not available.'}</p></div><p className="reasoning">{report.reasoning}</p><div className="evidence-references"><b>Evidence referenced</b><div>{report.rcaEvidenceIds?.map(id => <span className="evidence-chip" key={id}>{id}</span>) || report.investigationFindings.flatMap(x => x.evidenceIds).map(id => <span className="evidence-chip" key={id}>{id}</span>)}</div></div></div>
            <div className="panel metrics-panel"><div className="panel-header"><div><h2>Infrastructure signals</h2><p>{telemetryMode === 'real' ? 'Prometheus samples' : telemetryMode === 'mock' ? 'Scenario fixture values' : 'Source mode not recorded'}{telemetryWindow.startTime && telemetryWindow.endTime ? ` · ${time(telemetryWindow.startTime)} – ${time(telemetryWindow.endTime)}` : ''}</p></div><span className="count-badge">{report.infrastructureMetrics.length}</span></div><div className="metric-list">{report.infrastructureMetrics.map(metric => <div className="metric-row" key={metric.id}><div><b>{metric.name.replaceAll('_', ' ')}</b><small>{metric.id} · {metric.source || telemetryMode || 'unknown'}{metric.timestamp ? ` · ${time(metric.timestamp)}` : ''}{metric.recordCount ? ` · ${metric.recordCount} samples` : ''}</small></div><strong>{metric.value ?? metric.status ?? '—'}{metric.unit ? <small> {metric.unit}</small> : ''}</strong></div>)}</div><div className="subsection-head"><b>Application logs</b><span>{report.applicationLogs.length} entries</span></div><div className="logs-list">{report.applicationLogs.map(log => <div className="log-row" key={log.id}><span className={`log-level ${log.level.toLowerCase()}`}>{log.level}</span><div className="log-copy"><p>{log.message}</p><small>{time(log.timestamp)} · {log.service || detail.serviceName} · {log.source || telemetryMode || 'unknown'}</small></div></div>)}</div></div>
            <div className="panel mcp-panel"><div className="panel-header"><div><h2>MCP tool execution</h2><p>Discovered tools and calls made by the Investigation Agent</p></div><span className="count-badge">{mcpToolTrace.length} calls</span></div><div className="mcp-trace">{mcpToolTrace.length ? mcpToolTrace.map((tool, index) => <div className="mcp-trace-row" key={`${tool.toolName}-${index}`}><div className={`mcp-status ${tool.status.toLowerCase()}`}>{tool.status}</div><div className="mcp-copy"><b>{tool.toolName}</b><small>{tool.server}</small>{tool.error && <p>{tool.error}</p>}</div><div className="mcp-count"><b>{tool.recordCount}</b><small>records · {tool.durationMs} ms</small></div></div>) : <div className="empty">No MCP calls were recorded for this report.</div>}</div>{mcpToolCatalog.length > 0 && <details className="catalog-details"><summary>Tool catalog ({mcpToolCatalog.length} discovered)</summary><div>{mcpToolCatalog.map(tool => <article key={tool.name}><b>{tool.name}</b><p>{tool.description}</p><pre>{JSON.stringify(tool.inputSchema, null, 2)}</pre></article>)}</div></details>}</div>
            {Object.keys(telemetryEvidence).length > 0 && <div className="panel evidence-payload-panel"><div className="panel-header"><div><h2>Complete telemetry tool responses</h2><p>Raw data returned by Prometheus and Loki MCP tools</p></div><span className="count-badge">{Object.keys(telemetryEvidence).length} tool types</span></div>{Object.entries(telemetryEvidence).map(([toolName, payloads]) => <details className="payload-details" key={toolName}><summary>{toolName} · {payloads.reduce((total, payload) => total + (Number(payload.recordCount) || 0), 0)} records</summary>{payloads.map((payload, index) => <pre key={index}>{JSON.stringify(payload, null, 2)}</pre>)}</details>)}</div>}
            <div className="panel recommendations-panel"><div className="panel-header"><div><h2>Recommended actions</h2><p>Human review required · no actions executed</p></div></div>{report.recommendedActions.length ? report.recommendedActions.map((action, index) => <div className="action-card" key={`${action.title}-${index}`}><div className="action-heading"><span className="action-number">0{index + 1}</span><b>{action.title}</b><span className={`risk risk-${action.risk.toLowerCase()}`}>{action.risk} RISK</span></div><p>{action.description}</p><div className="impact"><b>Expected impact</b><span>{action.expectedImpact}</span></div><div className="verify"><b>Verification</b><ul>{action.verificationSteps.map(step => <li key={step}>{step}</li>)}</ul></div></div>) : <div className="empty">No recommendations returned.</div>}{reportErrors.length > 0 && <div className="error-list"><b>Workflow errors</b>{reportErrors.map(error => <p key={error}>{error}</p>)}</div>}</div>
          </div> : <div className="panel no-report"><span className="empty-icon">◷</span><div><b>No investigation report</b><p>The report will appear after the agent workflow completes.</p></div></div>}
        </section>}

        <footer className="page-footer"><span>NEXUS AI <i>·</i> Infrastructure operations platform</span><span>Phase 2 · Read-only observability demo</span></footer>
      </div>
    </main>

    {showForm && <div className="modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) setShowForm(false) }}><section className="modal"><div className="modal-heading"><div><div className="eyebrow">ALERT INTAKE</div><h2>Start an investigation</h2><p>Submit an alert for read-only analysis by the agent workflow.</p></div><button className="icon-button" onClick={() => setShowForm(false)} aria-label="Close">×</button></div><form onSubmit={submit} className="incident-form"><label>Service name<input required value={form.serviceName} onChange={e => setForm({ ...form, serviceName: e.target.value })}/></label><div className="form-row"><label>Environment<select value={form.environment} onChange={e => setForm({ ...form, environment: e.target.value })}><option>production</option><option>staging</option><option>development</option></select></label><label>Severity<select value={form.severity} onChange={e => setForm({ ...form, severity: e.target.value })}><option>CRITICAL</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option></select></label></div><label>Scenario<select value={form.alertType} onChange={e => { const alertType = e.target.value; const descriptions: Record<string, string> = { HIGH_CPU: 'CPU utilization exceeded 80% for 10 minutes', HIGH_MEMORY: 'Memory utilization is above 90% with repeated long GC pauses', DB_POOL_EXHAUSTION: 'Database connection pool exhausted with acquisition timeouts', DATABASE_LATENCY: 'Increased API latency caused by database delays', DEPENDENCY_FAILURE: 'Application errors caused by downstream dependency failures' }; setForm({ ...form, alertType, description: descriptions[alertType] }) }}><option value="HIGH_CPU">High CPU · excessive threads</option><option value="HIGH_MEMORY">High memory · GC pressure</option><option value="DB_POOL_EXHAUSTION">Database connection pool</option><option value="DATABASE_LATENCY">Database query latency</option><option value="DEPENDENCY_FAILURE">Downstream dependency failure</option></select></label><label>Alert description<textarea required rows={3} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}/></label><div className="form-hint">The backend queries its configured telemetry source (Prometheus/Loki or explicit mock fixtures). For live demo telemetry, trigger the selected scenario on the demo app first. No infrastructure changes are executed.</div><div className="modal-actions"><button type="button" className="secondary-button" onClick={() => setShowForm(false)}>Cancel</button><button type="submit" className="primary-button" disabled={submitting}>{submitting ? <><span className="spinner"/> Investigating…</> : 'Run investigation →'}</button></div></form></section></div>}
  </div>
}

function StatCard({ label, value, note, icon, tone }: { label: string; value: number; note: string; icon: string; tone: string }) {
  return <div className="stat-card"><div className={`stat-icon ${tone}`}>{icon}</div><div className="stat-copy"><span>{label}</span><b>{value}</b><small>{note}</small></div><span className="stat-spark">↗</span></div>
}
function Severity({ value }: { value: string }) { return <span className={`severity severity-${value.toLowerCase()}`}><i/> {value}</span> }
function Status({ value }: { value: string }) { return <span className={`status status-${value.toLowerCase()}`}><i/> {value}</span> }

