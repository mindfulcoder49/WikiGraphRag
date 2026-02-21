import { useEffect, useRef } from 'react'
import type { LogEntry } from '../types'

interface Props {
  logs: LogEntry[]
}

export default function BuildLog({ logs }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  return (
    <div className="build-log">
      <div className="log-header">Build Log</div>
      <div className="log-body">
        {logs.length === 0 && (
          <div className="log-empty">Waiting for events…</div>
        )}
        {logs.map((entry, i) => (
          <div key={i} className={`log-entry log-${entry.level}`}>
            <span className="log-ts">{formatTs(entry.ts)}</span>
            <span className="log-msg">{entry.message}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function formatTs(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString()
  } catch {
    return ts
  }
}
