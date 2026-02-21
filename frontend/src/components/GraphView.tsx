import { useCallback, useEffect, useRef, useState } from 'react'
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

interface FGNode {
  id: string
  label: string
  type: string
  color: string
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

  const gDataRef = useRef<{ nodes: FGNode[]; links: object[] }>({ nodes: [], links: [] })
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [graphData, setGraphData] = useState<{ nodes: any[]; links: any[] }>({ nodes: [], links: [] })

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

  // Incremental node additions
  useEffect(() => {
    const existingIds = new Set(gDataRef.current.nodes.map((n) => n.id))
    const newNodes = nodes
      .filter((n) => !existingIds.has(n.id))
      .map((n): FGNode => ({
        id: n.id,
        label: n.label,
        type: n.type,
        color: TYPE_COLORS[n.type] ?? '#757575',
      }))
    if (!newNodes.length) return
    gDataRef.current = { nodes: [...gDataRef.current.nodes, ...newNodes], links: gDataRef.current.links }
    setGraphData({ ...gDataRef.current })
  }, [nodes])

  // Incremental link additions
  useEffect(() => {
    const existingIds = new Set((gDataRef.current.links as { id: string }[]).map((l) => l.id))
    const newLinks = edges
      .filter((e) => !existingIds.has(e.id))
      .map((e) => ({ id: e.id, source: e.source, target: e.target, label: e.label, confidence: e.confidence }))
    if (!newLinks.length) return
    gDataRef.current = { nodes: gDataRef.current.nodes, links: [...gDataRef.current.links, ...newLinks] }
    setGraphData({ ...gDataRef.current })
  }, [edges])

  const handleNodeClick = useCallback(
    (node: object) => { onNodeClick((node as FGNode).id) },
    [onNodeClick],
  )

  // Build a SpriteText label that sits just above the node sphere
  const makeLabelObject = useCallback((node: object) => {
    const n = node as FGNode
    const sprite = new SpriteText(n.label)
    sprite.color = '#ffffff'
    sprite.textHeight = 3.5
    sprite.backgroundColor = 'rgba(0,0,0,0.55)'
    sprite.padding = 1.5
    sprite.borderRadius = 2
    sprite.position.y = 9  // offset above sphere (nodeRelSize = 6)
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
        />
      </div>
    </div>
  )
}
