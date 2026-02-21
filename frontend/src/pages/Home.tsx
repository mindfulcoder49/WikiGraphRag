import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createBuild, listBuilds } from '../api'
import type { BuildInfo } from '../types'

const DEMO_TOPICS = ['Ada Lovelace', 'Python (programming language)', 'Climate change', 'Marie Curie']

function timeAgo(iso: string | null): string {
  if (!iso) return ''
  const secs = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (secs < 60) return 'just now'
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`
  return `${Math.floor(secs / 86400)}d ago`
}

export default function Home() {
  const navigate = useNavigate()
  const [topic, setTopic] = useState('')
  const [maxPages, setMaxPages] = useState(15)
  const [maxDepth, setMaxDepth] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [builds, setBuilds] = useState<BuildInfo[]>([])

  useEffect(() => {
    listBuilds()
      .then(setBuilds)
      .catch(() => {})
  }, [])

  async function handleBuild() {
    const t = topic.trim()
    if (!t) return
    setLoading(true)
    setError(null)
    try {
      const { build_id } = await createBuild(t, maxPages, maxDepth)
      navigate(`/build/${build_id}`)
    } catch (e) {
      setError(String(e))
      setLoading(false)
    }
  }

  return (
    <div className="home-page">
      <div className="home-layout">
        {/* ── Create form ── */}
        <div className="home-card">
          <div className="home-logo">🕸️</div>
          <h1>WikiGraph RAG</h1>
          <p className="home-subtitle">
            Build a live knowledge graph from Wikipedia and ask grounded questions.
          </p>

          <div className="form-group">
            <label htmlFor="topic">Topic</label>
            <input
              id="topic"
              type="text"
              className="topic-input"
              placeholder="e.g. Ada Lovelace"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleBuild()}
              disabled={loading}
            />
            <div className="demo-topics">
              {DEMO_TOPICS.map((t) => (
                <button
                  key={t}
                  className="chip"
                  onClick={() => setTopic(t)}
                  disabled={loading}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div className="sliders">
            <div className="slider-row">
              <label>Max Pages: <strong>{maxPages}</strong></label>
              <input
                type="range"
                min={3}
                max={50}
                value={maxPages}
                onChange={(e) => setMaxPages(Number(e.target.value))}
                disabled={loading}
              />
            </div>
            <div className="slider-row">
              <label>Crawl Depth: <strong>{maxDepth}</strong></label>
              <input
                type="range"
                min={0}
                max={3}
                value={maxDepth}
                onChange={(e) => setMaxDepth(Number(e.target.value))}
                disabled={loading}
              />
              <span className="hint">
                {maxDepth === 0 ? 'Seed page only' : `Seed + ${maxDepth} hop${maxDepth > 1 ? 's' : ''}`}
              </span>
            </div>
          </div>

          {error && <div className="error-box">{error}</div>}

          <button
            className="build-btn"
            onClick={handleBuild}
            disabled={loading || !topic.trim()}
          >
            {loading ? 'Starting…' : '🔨 Build Graph'}
          </button>
        </div>

        {/* ── Existing builds ── */}
        {builds.length > 0 && (
          <div className="builds-list-panel">
            <h2 className="builds-list-heading">Recent Builds</h2>
            <div className="builds-list">
              {builds.map((b) => (
                <button
                  key={b.id}
                  className="build-list-item"
                  onClick={() => navigate(`/build/${b.id}`)}
                >
                  <div className="bli-top">
                    <span className="bli-topic">{b.topic}</span>
                    <span className={`status-badge status-${b.status.toLowerCase()}`}>
                      {b.status}
                    </span>
                  </div>
                  <div className="bli-meta">
                    <span>{b.pages_processed} / {b.max_pages} pages</span>
                    <span>depth {b.max_depth}</span>
                    <span>{timeAgo(b.started_at)}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
