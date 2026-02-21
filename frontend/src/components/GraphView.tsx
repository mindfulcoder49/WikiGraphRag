import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ForceGraph3D from 'react-force-graph-3d'
import SpriteText from 'three-spritetext'
import type { GraphEdge, GraphNode } from '../types'

const TYPE_COLORS: Record<string, string> = {
  Person: '#4285F4',
  Organization: '#34A853',
  Place: '#FF6D00',
  Work: '#9C27B0',
  Concept: '#00BCD4',
  Event: '#F44336',
  Institution: '#FF9800',
  Other: '#757575',
}

interface Props {
  nodes: GraphNode[]
  edges: GraphEdge[]
  onNodeClick: (nodeId: string) => void
}

export default function GraphView({ nodes, edges, onNodeClick }: Props) {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const [dims, setDims] = useState({ width: 800, height: 600 })
  const [showLabels, setShowLabels] = useState(true)

  // Track container size
  useEffect(() => {
    const el = wrapperRef.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      if (width > 0 && height > 0) setDims({ width, height })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Assign random initial positions only to nodes the library hasn't seen yet.
  // react-force-graph-3d preserves existing node positions via ID-based merging,
  // so we must NOT pass x/y/z for already-known nodes (it would teleport them).
  // Nodes starting at the origin (0,0,0) don't spread correctly because the
  // repulsive forces cancel — random initial positions fix this without needing
  // warmupTicks to do all the work.
  const seenNodeIds = useRef<Set<string>>(new Set())
  const initPositions = useRef<Map<string, { x: number; y: number; z: number }>>(new Map())

  const graphData = useMemo(() => {
    const SPREAD = 250
    // Build a set of known node IDs so we can filter dangling edges.
    // Dangling edges (where source or target node doesn't exist yet) crash the
    // d3-force link initializer with "node not found". This can happen when
    // WebSocket edge events arrive before the corresponding node events, or when
    // the REST API snapshot has referential inconsistencies.
    const nodeIds = new Set(nodes.map((n) => n.id))
    return {
      nodes: nodes.map((n) => {
        const isNew = !seenNodeIds.current.has(n.id)
        if (isNew) {
          seenNodeIds.current.add(n.id)
          initPositions.current.set(n.id, {
            x: (Math.random() - 0.5) * SPREAD,
            y: (Math.random() - 0.5) * SPREAD,
            z: (Math.random() - 0.5) * SPREAD,
          })
        }
        const base = {
          id: n.id,
          label: n.label,
          type: n.type,
          color: TYPE_COLORS[n.type] ?? '#757575',
        }
        // Only supply initial position for brand-new nodes
        return isNew ? { ...base, ...initPositions.current.get(n.id)! } : base
      }),
      links: edges
        .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
        .map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.label,
        })),
    }
  }, [nodes, edges])

  const handleNodeClick = useCallback(
    (node: object) => { onNodeClick((node as { id: string }).id) },
    [onNodeClick],
  )

  const makeLabelObject = useCallback((node: object) => {
    const sprite = new SpriteText((node as { label: string }).label)
    sprite.color = '#ffffff'
    sprite.textHeight = 3.5
    sprite.backgroundColor = 'rgba(0,0,0,0.55)'
    sprite.padding = 1.5
    sprite.borderRadius = 2
    sprite.position.y = 9
    return sprite
  }, [])

  return (
    <div className="graph-wrapper">
      <div className="graph-legend">
        {Object.entries(TYPE_COLORS).map(([type, color]) => (
          <span key={type} className="legend-item">
            <span className="legend-dot" style={{ background: color }} />
            {type}
          </span>
        ))}
        <button
          className={`label-toggle ${showLabels ? 'label-toggle--on' : ''}`}
          onClick={() => setShowLabels((v) => !v)}
          title="Toggle node labels"
        >
          {showLabels ? 'Labels on' : 'Labels off'}
        </button>
      </div>

      <div ref={wrapperRef} style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>
        <ForceGraph3D
          graphData={graphData}
          width={dims.width}
          height={dims.height}
          nodeId="id"
          nodeLabel="label"
          nodeColor="color"
          nodeRelSize={6}
          nodeThreeObjectExtend={showLabels}
          nodeThreeObject={showLabels ? makeLabelObject : undefined}
          linkLabel="label"
          linkDirectionalArrowLength={4}
          linkDirectionalArrowRelPos={1}
          linkColor={() => 'rgba(255,255,255,0.15)'}
          linkWidth={0.8}
          backgroundColor="#0d1117"
          onNodeClick={handleNodeClick}
          cooldownTicks={500}
        />
      </div>
    </div>
  )
}
