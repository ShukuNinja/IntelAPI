import type { Campaign, Finding, HealthCheck, Metric } from './types'

export const metrics: Metric[] = [
  { label: 'Requests executed', value: '1,284', change: 'Demo data', tone: 'neutral' },
  { label: 'Endpoints mapped', value: '42', change: 'Across 3 specs', tone: 'neutral' },
  { label: 'Open findings', value: '08', change: 'Demo data', tone: 'warning' },
  { label: 'Active campaigns', value: '02', change: 'Simulated state', tone: 'positive' },
]

export const healthChecks: HealthCheck[] = [
  { id: 'hc-01', name: 'Users API', method: 'GET', endpoint: '/api/v1/users', status: 'Healthy', latency: 84, lastChecked: '2 min ago' },
  { id: 'hc-02', name: 'Orders API', method: 'GET', endpoint: '/api/v1/orders', status: 'Degraded', latency: 612, lastChecked: '4 min ago' },
  { id: 'hc-03', name: 'Auth API', method: 'POST', endpoint: '/api/v1/auth/token', status: 'Healthy', latency: 126, lastChecked: '5 min ago' },
  { id: 'hc-04', name: 'Reports API', method: 'GET', endpoint: '/api/v1/reports', status: 'Not checked', latency: null, lastChecked: 'Never' },
]

export const findings: Finding[] = [
  { id: 'FND-104', title: 'Undocumented 500 response', severity: 'High', endpoint: 'GET /api/v1/orders/{id}', category: 'Contract mismatch', status: 'Open', summary: 'Observed response status is not listed in the imported specification. This is an observation, not yet a confirmed defect.', observedAt: 'Today, 10:42' },
  { id: 'FND-103', title: 'Response field type differs', severity: 'Medium', endpoint: 'GET /api/v1/users/{id}', category: 'Schema mismatch', status: 'Triaged', summary: 'The field `created_at` was a number in one captured response but is documented as a string.', observedAt: 'Today, 09:18' },
  { id: 'FND-101', title: 'Slow response at boundary input', severity: 'Low', endpoint: 'GET /api/v1/search', category: 'Performance signal', status: 'Open', summary: 'A boundary-sized query returned slower than the baseline. More repetitions are needed to confirm.', observedAt: 'Yesterday' },
]

export const campaigns: Campaign[] = [
  { id: 'CMP-008', name: 'Orders API exploration', target: 'Orders Service', status: 'Running', tests: 68, findings: 4, updatedAt: '3 min ago' },
  { id: 'CMP-007', name: 'Users contract validation', target: 'Users Service', status: 'Completed', tests: 124, findings: 3, updatedAt: 'Yesterday' },
  { id: 'CMP-006', name: 'Auth negative paths', target: 'Auth Service', status: 'Draft', tests: 0, findings: 0, updatedAt: 'Oct 14' },
]