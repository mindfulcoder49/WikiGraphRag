export interface GraphNode {
  id: string
  label: string
  type: string
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  label: string
  claim_id: string
  confidence: number
}

export interface LogEntry {
  level: 'info' | 'warn' | 'error'
  message: string
  ts: string
}

export interface ProgressState {
  pages_processed: number
  queue_size: number
  max_pages: number
}

export type BuildStatus = 'RUNNING' | 'DONE' | 'ERROR' | 'STOPPED'

export interface BuildInfo {
  id: string
  topic: string
  status: BuildStatus
  started_at: string | null
  finished_at: string | null
  max_pages: number
  max_depth: number
  pages_processed: number
  queue_size: number
}

export type BuildEvent =
  | { type: 'log'; level: string; message: string; ts: string }
  | { type: 'progress'; pages_processed: number; queue_size: number; max_pages: number }
  | { type: 'graph.add_nodes'; nodes: GraphNode[] }
  | { type: 'graph.add_edges'; edges: GraphEdge[] }
  | { type: 'done'; build_id: string; pages_processed: number; entity_count: number; claim_count: number }
  | { type: 'error'; build_id: string; message: string }

export interface Citation {
  chunk_id: string
  page_title: string
  section: string
  snippet: string
  url: string
}

export interface AnswerResponse {
  answer_text: string
  citations: Citation[]
  used_entities: string[]
  used_claim_ids: string[]
  suggest_expand: boolean
  followup_pages: string[]
}

export interface EntityDetail {
  entity: {
    id: string
    name: string
    canonical_name: string
    type: string
    description: string | null
  }
  claims: Array<{
    claim_id: string
    predicate: string
    object_text: string | null
    confidence: number
    chunk_id: string | null
    snippet: string | null
    section: string | null
    page_title: string | null
    url: string | null
  }>
  related: Array<{
    id: string
    name: string
    rel_type: string
    confidence: number
  }>
}
