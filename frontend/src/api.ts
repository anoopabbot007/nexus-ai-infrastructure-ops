import axios from 'axios'

export type Metric = { id: string; name: string; value?: number | string; unit?: string; status?: string; baseline?: number; source?: string; timestamp?: string; recordCount?: number }
export type LogEntry = { id: string; timestamp: string; level: string; message: string; source?: string; service?: string; environment?: string }
export type Finding = { title: string; summary: string; evidenceIds: string[] }
export type Action = { title: string; description: string; expectedImpact: string; risk: 'LOW' | 'MEDIUM' | 'HIGH'; verificationSteps: string[] }
export type AgentStep = { agentName: string; status: string; startedAt: string; completedAt: string; summary: string }
export type MCPToolTrace = { toolName: string; server: string; status: string; durationMs: number; recordCount: number; error?: string | null }
export type MCPTool = { name: string; description?: string; inputSchema?: Record<string, unknown> }
export type TelemetryPayload = Record<string, unknown>
export type Report = {
  incidentId: string; severity: string; affectedService: string; investigationParameters: string[];
  infrastructureMetrics: Metric[]; applicationLogs: LogEntry[]; investigationFindings: Finding[];
  probableRootCause: string; rcaEvidenceIds: string[]; confidenceScore: number; reasoning: string; recommendedActions: Action[];
  executionStatus: string; errors: string[]; executionTrace: AgentStep[]; llmProvider: string;
  telemetryMode: 'real' | 'mock'; telemetryWindow: { startTime?: string; endTime?: string };
  telemetryEvidence: Record<string, TelemetryPayload[]>; mcpToolTrace: MCPToolTrace[]; mcpToolCatalog: MCPTool[]
}
export type Incident = {
  incidentId: string; serviceName: string; environment: string; alertType: string; severity: string;
  description: string; status: string; createdAt: string; updatedAt: string; investigation?: Report | null
}
export type NewIncident = {
  serviceName: string; environment: string; alertType: string; cpuUtilization?: number;
  threshold?: number; severity: string; description: string
}

export const api = axios.create({ baseURL: '/api/v1', timeout: 60000, headers: { 'Content-Type': 'application/json' } })
export const getIncidents = async () => (await api.get<Incident[]>('/incidents')).data
export const getIncident = async (id: string) => (await api.get<Incident>(`/incidents/${encodeURIComponent(id)}`)).data
export const createIncident = async (body: NewIncident) => (await api.post<Incident>('/incidents', body)).data

