import type { EntityDetail } from '../types'

interface Props {
  detail: EntityDetail
  onClose: () => void
}

const TYPE_ICONS: Record<string, string> = {
  Person: '👤',
  Organization: '🏢',
  Place: '📍',
  Work: '📚',
  Concept: '💡',
  Event: '📅',
  Institution: '🏛️',
  Other: '🔷',
}

export default function NodeDrawer({ detail, onClose }: Props) {
  const { entity, claims, related } = detail
  const icon = TYPE_ICONS[entity.type] ?? '🔷'

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <button className="drawer-close" onClick={onClose}>✕</button>

        <div className="drawer-header">
          <span className="drawer-icon">{icon}</span>
          <div>
            <div className="drawer-name">{entity.name}</div>
            <div className="drawer-type">{entity.type}</div>
          </div>
        </div>

        {entity.description && (
          <p className="drawer-desc">{entity.description}</p>
        )}

        {related.length > 0 && (
          <section className="drawer-section">
            <h4>Related Entities</h4>
            <ul className="related-list">
              {related.map((r) => (
                <li key={r.id}>
                  <span className="rel-type">{r.rel_type}</span>
                  <span className="rel-name">{r.name}</span>
                  <span className="rel-conf">{Math.round((r.confidence ?? 0) * 100)}%</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {claims.length > 0 && (
          <section className="drawer-section">
            <h4>Claims ({claims.length})</h4>
            <ul className="claims-list">
              {claims.map((c) => (
                <li key={c.claim_id} className="claim-item">
                  <div className="claim-predicate">{c.predicate}</div>
                  {c.object_text && <div className="claim-object">{c.object_text}</div>}
                  {c.snippet && (
                    <div className="claim-snippet">
                      <em>"{c.snippet}"</em>
                      {c.url && (
                        <a href={c.url} target="_blank" rel="noreferrer" className="claim-link">
                          {c.page_title}
                        </a>
                      )}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  )
}
