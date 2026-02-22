import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getBuild, getBuildLogs, getGraph, getEntities, getEntity, openBuildWebSocket, stopBuild } from '../api'
import type {
  BuildEvent,
  BuildStatus,
  GraphNode,
  GraphEdge,
  LogEntry,
  ProgressState,
  EntityDetail,
} from '../types'
import BuildLog from '../components/BuildLog'
import ProgressBar from '../components/ProgressBar'
import GraphView from '../components/GraphView'
import NodeDrawer from '../components/NodeDrawer'
import NodeSidebar from '../components/NodeSidebar'
import Chat from '../components/Chat'

export default function Build() {
  const { buildId } = useParams<{ buildId: string }>()
  const [status, setStatus] = useState<BuildStatus>('RUNNING')
  const [topic, setTopic] = useState('')
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [progress, setProgress] = useState<ProgressState>({ pages_processed: 0, queue_size: 0, max_pages: 15 })
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [edges, setEdges] = useState<GraphEdge[]>([])
  const [allEntities, setAllEntities] = useState<Array<{ id: string; name: string; type: string }>>([])
  const [selectedEntity, setSelectedEntity] = useState<EntityDetail | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [stats, setStats] = useState<{ entity_count: number; claim_count: number } | null>(null)

  const wsRef = useRef<WebSocket | null>(null)

  // ── 1. Load initial build info on mount ───────────────────────────────────
  useEffect(() => {
    if (!buildId) return
    getBuild(buildId)
      .then((b) => {
        setTopic(b.topic)
        setStatus(b.status)
        setProgress({
          pages_processed: b.pages_processed,
          queue_size: b.queue_size,
          max_pages: b.max_pages,
        })
      })
      .catch(console.error)
  }, [buildId])

  // ── 2. Load persisted build logs on mount ─────────────────────────────────
  useEffect(() => {
    if (!buildId) return
    getBuildLogs(buildId)
      .then((persisted) => { if (persisted.length > 0) setLogs(persisted) })
      .catch(() => {})
  }, [buildId])

  // ── 4. Always load the current graph snapshot from the REST API on mount ──
  //    This ensures nodes processed before the WebSocket connected are shown,
  //    and lets the user refresh mid-build without losing the graph.
  useEffect(() => {
    if (!buildId) return
    getGraph(buildId)
      .then((g) => {
        if (g.nodes.length > 0) {
          setNodes(g.nodes)
          setEdges(g.edges)
        }
      })
      .catch(() => {}) // empty graph is fine
  }, [buildId])

  // ── 4b. Load all entities (sidebar list – no graph limit) ─────────────────
  const refreshAllEntities = useCallback(() => {
    if (!buildId) return
    getEntities(buildId).then(setAllEntities).catch(() => {})
  }, [buildId])

  useEffect(() => {
    refreshAllEntities()
  }, [refreshAllEntities])

  // ── 5. WebSocket for live updates ─────────────────────────────────────────
  useEffect(() => {
    if (!buildId) return

    // Track whether the socket was ever successfully opened.
    // In React StrictMode (dev) effects run twice: the first socket is
    // torn down before the handshake completes, causing a spurious onerror.
    // We suppress that error so the log stays clean.
    let wasOpen = false

    const ws = openBuildWebSocket(buildId)
    wsRef.current = ws

    ws.onopen = () => {
      wasOpen = true
    }

    ws.onmessage = (evt) => {
      const event = JSON.parse(evt.data) as BuildEvent
      handleEvent(event)
    }

    ws.onerror = () => {
      if (wasOpen) {
        addLog({ level: 'warn', message: 'WebSocket connection lost.', ts: new Date().toISOString() })
      }
    }

    ws.onclose = (evt) => {
      // Unexpected close after a successful open (not a clean client-side close)
      if (wasOpen && evt.code !== 1000) {
        addLog({ level: 'warn', message: `WebSocket closed (code ${evt.code}). Refresh to reconnect.`, ts: new Date().toISOString() })
      }
    }

    return () => {
      ws.close()
    }
  }, [buildId]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleEvent(event: BuildEvent) {
    switch (event.type) {
      case 'log':
        addLog({ level: event.level as LogEntry['level'], message: event.message, ts: event.ts })
        break
      case 'progress':
        setProgress({ pages_processed: event.pages_processed, queue_size: event.queue_size, max_pages: event.max_pages })
        break
      case 'graph.add_nodes':
        setNodes((prev) => {
          const existingIds = new Set(prev.map((n) => n.id))
          const newOnes = event.nodes.filter((n) => !existingIds.has(n.id))
          return newOnes.length ? [...prev, ...newOnes] : prev
        })
        setAllEntities((prev) => {
          const existingIds = new Set(prev.map((e) => e.id))
          const newOnes = event.nodes
            .filter((n) => !existingIds.has(n.id))
            .map((n) => ({ id: n.id, name: n.label, type: n.type }))
          return newOnes.length ? [...prev, ...newOnes].sort((a, b) => a.name.localeCompare(b.name)) : prev
        })
        break
      case 'graph.add_edges':
        setEdges((prev) => {
          const existingIds = new Set(prev.map((e) => e.id))
          const newOnes = event.edges.filter((e) => !existingIds.has(e.id))
          return newOnes.length ? [...prev, ...newOnes] : prev
        })
        break
      case 'done':
        setStatus('DONE')
        setStats({ entity_count: event.entity_count, claim_count: event.claim_count })
        addLog({ level: 'info', message: `✅ Done! ${event.entity_count} entities, ${event.claim_count} claims.`, ts: new Date().toISOString() })
        // Pull the final graph snapshot so nothing is missed
        if (buildId) {
          getGraph(buildId).then((g) => {
            setNodes(g.nodes)
            setEdges(g.edges)
          }).catch(() => {})
          refreshAllEntities()
        }
        break
      case 'error':
        setStatus('ERROR')
        addLog({ level: 'error', message: `Error: ${event.message}`, ts: new Date().toISOString() })
        break
    }
  }

  function addLog(entry: LogEntry) {
    setLogs((prev) => [...prev.slice(-499), entry])
  }

  const handleNodeClick = useCallback(async (nodeId: string) => {
    if (!buildId) return
    try {
      const detail = await getEntity(buildId, nodeId)
      setSelectedEntity(detail)
      setDrawerOpen(true)
    } catch {
      // entity might not have detail yet
    }
  }, [buildId])

  async function handleStop() {
    if (!buildId) return
    await stopBuild(buildId)
    setStatus('STOPPED')
  }

  return (
    <div className="build-page">
      {/* Header */}
      <div className="build-header">
        <Link to="/" className="back-link">← Home</Link>
        <div className="build-title">
          <span className="build-topic">{topic}</span>
          <span className={`status-badge status-${status.toLowerCase()}`}>{status}</span>
        </div>
        {status === 'RUNNING' && (
          <button className="stop-btn" onClick={handleStop}>Stop</button>
        )}
        {stats && (
          <div className="build-stats">
            {stats.entity_count} entities · {stats.claim_count} claims
          </div>
        )}
      </div>

      {/* Progress */}
      <ProgressBar progress={progress} />

      {/* Main layout */}
      <div className="build-body">
        {/* Left: log */}
        <div className="build-left">
          <BuildLog logs={logs} />
        </div>

        {/* Right: graph + node sidebar */}
        <div className="build-right">
          <GraphView
            nodes={nodes}
            edges={edges}
            onNodeClick={handleNodeClick}
          />
          <NodeSidebar nodes={allEntities} onNodeClick={handleNodeClick} />
        </div>
      </div>

      {/* Node detail drawer */}
      {drawerOpen && selectedEntity && (
        <NodeDrawer
          detail={selectedEntity}
          onClose={() => setDrawerOpen(false)}
        />
      )}

      {/* Chat (after done or stopped) */}
      {(status === 'DONE' || status === 'STOPPED') && buildId && (
        <div className="chat-section">
          <Chat buildId={buildId} />
        </div>
      )}
    </div>
  )
}
