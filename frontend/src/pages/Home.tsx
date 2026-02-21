import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createBuild } from '../api'

const DEMO_TOPICS = ['Ada Lovelace', 'Python (programming language)', 'Climate change', 'Marie Curie']

export default function Home() {
  const navigate = useNavigate()
  const [topic, setTopic] = useState('')
  const [maxPages, setMaxPages] = useState(15)
  const [maxDepth, setMaxDepth] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
    </div>
  )
}
