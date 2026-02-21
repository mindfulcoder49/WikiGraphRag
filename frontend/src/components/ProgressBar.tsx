import type { ProgressState } from '../types'

interface Props {
  progress: ProgressState
}

export default function ProgressBar({ progress }: Props) {
  const { pages_processed, max_pages, queue_size } = progress
  const pct = max_pages > 0 ? Math.min(100, Math.round((pages_processed / max_pages) * 100)) : 0

  return (
    <div className="progress-bar-wrapper">
      <div className="progress-info">
        <span>
          Pages: <strong>{pages_processed}</strong> / {max_pages}
        </span>
        <span>Queue: <strong>{queue_size}</strong></span>
        <span>{pct}%</span>
      </div>
      <div className="progress-track">
        <div
          className="progress-fill"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
