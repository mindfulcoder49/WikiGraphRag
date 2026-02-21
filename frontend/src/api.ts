import type { AnswerResponse, BuildInfo, EntityDetail, LogEntry } from './types'

// In local dev the docker-compose sets VITE_API_URL / VITE_WS_URL so the
// browser can reach the backend on a different port.  In production (Fly.io)
// those vars are not set at build time, so we fall back to same-origin URLs
// which work because the backend serves the frontend bundle itself.
const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ''
const WS_BASE =
  (import.meta.env.VITE_WS_URL as string | undefined) ??
  `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API ${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

export async function createBuild(
  topic: string,
  maxPages: number,
  maxDepth: number,
): Promise<{ build_id: string; status: string }> {
  return apiFetch('/api/builds', {
    method: 'POST',
    body: JSON.stringify({ topic, max_pages: maxPages, max_depth: maxDepth }),
  })
}

export async function listBuilds(): Promise<BuildInfo[]> {
  const data = await apiFetch<{ builds: BuildInfo[] }>('/api/builds')
  return data.builds ?? []
}

export async function getBuild(buildId: string): Promise<BuildInfo> {
  return apiFetch(`/api/builds/${buildId}`)
}

export async function stopBuild(buildId: string): Promise<void> {
  await apiFetch(`/api/builds/${buildId}/stop`, { method: 'POST' })
}

export async function getGraph(
  buildId: string,
  opts?: { centerEntityId?: string; depth?: number; limit?: number },
): Promise<{ nodes: import('./types').GraphNode[]; edges: import('./types').GraphEdge[] }> {
  const params = new URLSearchParams()
  if (opts?.centerEntityId) params.set('center_entity_id', opts.centerEntityId)
  if (opts?.depth !== undefined) params.set('depth', String(opts.depth))
  if (opts?.limit !== undefined) params.set('limit', String(opts.limit))
  const qs = params.toString()
  return apiFetch(`/api/builds/${buildId}/graph${qs ? '?' + qs : ''}`)
}

export async function getEntity(buildId: string, entityId: string): Promise<EntityDetail> {
  return apiFetch(`/api/builds/${buildId}/entity/${entityId}`)
}

export async function askQuestion(
  buildId: string,
  question: string,
  history: Array<{ role: 'user' | 'assistant'; content: string }> = [],
): Promise<AnswerResponse> {
  return apiFetch(`/api/builds/${buildId}/ask`, {
    method: 'POST',
    body: JSON.stringify({ question, history }),
  })
}

export async function getBuildLogs(buildId: string): Promise<LogEntry[]> {
  try {
    const data = await apiFetch<{ logs: LogEntry[] }>(`/api/builds/${buildId}/logs`)
    return data.logs ?? []
  } catch {
    return []
  }
}

export function openBuildWebSocket(buildId: string): WebSocket {
  return new WebSocket(`${WS_BASE}/ws/build/${buildId}`)
}
