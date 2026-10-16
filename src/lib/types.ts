export type Severity = 'Critical' | 'High' | 'Medium' | 'Low'
export type HealthState = 'Healthy' | 'Degraded' | 'Unavailable' | 'Not checked'

export interface Metric {
  label: string
  value: string
  change?: string
  tone?: 'neutral' | 'positive' | 'warning' | 'danger'
}

export interface HealthCheck {
  id: string
  name: string
  method: string
  endpoint: string
  status: HealthState
  latency: number | null
  lastChecked: string
}

export interface Finding {
  id: string
  title: string
  severity: Severity
  endpoint: string
  category: string
  status: 'Open' | 'Triaged' | 'Resolved'
  summary: string
  observedAt: string
}

export interface Campaign {
  id: string
  name: string
  target: string
  status: 'Draft' | 'Running' | 'Completed' | 'Paused'
  tests: number
  findings: number
  updatedAt: string
}