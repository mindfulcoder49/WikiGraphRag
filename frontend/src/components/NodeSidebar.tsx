import { useState, useMemo } from 'react'

const TYPE_COLORS: Record<string, string> = {
  Person:       '#e06c75',
  Organization: '#e5c07b',
  Place:        '#61afef',
  Work:         '#c678dd',
  Concept:      '#56b6c2',
  Event:        '#d19a66',
  Institution:  '#98c379',
  Other:        '#757575',
}

interface EntityItem {
  id: string
  name: string
  type: string
}

interface Props {
  nodes: EntityItem[]
  onNodeClick: (id: string) => void
}

export default function NodeSidebar({ nodes, onNodeClick }: Props) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    const list = q
      ? nodes.filter((n) => n.name.toLowerCase().includes(q))
      : nodes
    // allEntities comes pre-sorted from the API; only re-sort when searching
    return q ? [...list].sort((a, b) => a.name.localeCompare(b.name)) : list
  }, [nodes, search])

  return (
    <div className={`node-sidebar${open ? ' node-sidebar--open' : ''}`}>
      <button
        className="node-sidebar-toggle"
        onClick={() => setOpen((v) => !v)}
        title={open ? 'Collapse node list' : 'Expand node list'}
      >
        {open ? '✕' : '☰'}
        {!open && nodes.length > 0 && (
          <span className="node-sidebar-count">{nodes.length}</span>
        )}
      </button>

      {open && (
        <div className="node-sidebar-panel">
          <div className="node-sidebar-header">
            <span className="node-sidebar-title">Entities</span>
            <span className="node-sidebar-total">{nodes.length}</span>
          </div>

          <input
            className="node-sidebar-search"
            type="text"
            placeholder="Search…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            autoFocus
          />

          <div className="node-sidebar-list">
            {filtered.length === 0 && (
              <div className="node-sidebar-empty">No entities found</div>
            )}
            {filtered.map((n) => (
              <button
                key={n.id}
                className="node-sidebar-item"
                onClick={() => onNodeClick(n.id)}
                title={n.type}
              >
                <span
                  className="node-sidebar-dot"
                  style={{ background: TYPE_COLORS[n.type] ?? '#757575' }}
                />
                <span className="node-sidebar-label">{n.name}</span>
                <span className="node-sidebar-type">{n.type}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
