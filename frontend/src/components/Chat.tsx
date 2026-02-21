import { useState, useRef, useEffect } from 'react'
import { askQuestion } from '../api'
import type { AnswerResponse, Citation } from '../types'

interface Message {
  role: 'user' | 'assistant'
  text: string
  answer?: AnswerResponse
}

interface Props {
  buildId: string
}

export default function Chat({ buildId }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState<Citation | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSend() {
    const q = input.trim()
    if (!q || loading) return
    setInput('')
    setLoading(true)

    // Snapshot current messages before adding the new user turn so we can
    // build the history to send (prior exchanges only, not the current question).
    const history = messages.map((m) => ({
      role: m.role,
      content: m.text,
    }))

    setMessages((prev) => [...prev, { role: 'user', text: q }])
    try {
      const answer = await askQuestion(buildId, q, history)
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: answer.answer_text, answer },
      ])
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: `Error: ${String(e)}` },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat">
      <div className="chat-header">💬 Ask about the graph</div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            Graph is ready. Ask a question grounded in the Wikipedia knowledge graph.
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`chat-msg chat-msg-${msg.role}`}>
            {msg.role === 'user' ? (
              <span>{msg.text}</span>
            ) : (
              <AssistantMessage
                answer={msg.answer}
                text={msg.text}
                onCitationClick={setModal}
              />
            )}
          </div>
        ))}
        {loading && (
          <div className="chat-msg chat-msg-assistant">
            <span className="thinking">Thinking…</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-row">
        <input
          type="text"
          className="chat-input"
          placeholder="Ask a question…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          disabled={loading}
        />
        <button
          className="chat-send-btn"
          onClick={handleSend}
          disabled={loading || !input.trim()}
        >
          Send
        </button>
      </div>

      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setModal(null)}>✕</button>
            <div className="modal-title">
              <a href={modal.url} target="_blank" rel="noreferrer">{modal.page_title}</a>
              <span className="modal-section">§ {modal.section}</span>
            </div>
            <blockquote className="modal-snippet">{modal.snippet}</blockquote>
            <div className="modal-chunk-id">Chunk: {modal.chunk_id}</div>
          </div>
        </div>
      )}
    </div>
  )
}

function AssistantMessage({
  answer,
  text,
  onCitationClick,
}: {
  answer?: AnswerResponse
  text: string
  onCitationClick: (c: Citation) => void
}) {
  if (!answer) return <span>{text}</span>

  // Build citation map by chunk_id for quick lookup
  const citationMap = new Map<string, Citation>(
    answer.citations.map((c) => [c.chunk_id, c]),
  )

  // Replace [chunk_id] markers with clickable spans
  const parts = text.split(/(\[chunk_[a-z0-9_]+\])/g)

  return (
    <div>
      <p className="answer-text">
        {parts.map((part, i) => {
          const match = part.match(/^\[(.+)\]$/)
          if (match) {
            const cid = match[1]
            const citation = citationMap.get(cid)
            if (citation) {
              return (
                <button
                  key={i}
                  className="citation-chip"
                  onClick={() => onCitationClick(citation)}
                  title={citation.page_title}
                >
                  [{citation.page_title}]
                </button>
              )
            }
          }
          return <span key={i}>{part}</span>
        })}
      </p>

      {answer.suggest_expand && (
        <div className="expand-hint">
          ℹ️ The graph may not have enough data. Consider rebuilding with more pages or depth.
          {answer.followup_pages.length > 0 && (
            <span> Suggested: {answer.followup_pages.join(', ')}</span>
          )}
        </div>
      )}

      {answer.citations.length > 0 && (
        <div className="citation-list">
          <strong>Sources:</strong>
          {answer.citations.map((c) => (
            <button
              key={c.chunk_id}
              className="citation-chip"
              onClick={() => onCitationClick(c)}
            >
              {c.page_title} § {c.section}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
