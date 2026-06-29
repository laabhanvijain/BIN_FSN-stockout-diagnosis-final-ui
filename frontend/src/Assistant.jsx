import { useState } from 'react'
import { askQuestion } from './api'

const ROUTE_BADGE = {
  SQL_ONLY:    { label: 'SQL',       cls: 'route-sql' },
  GRAPH_ONLY:  { label: 'Graph',     cls: 'route-graph' },
  SQL_GRAPH:   { label: 'SQL+Graph', cls: 'route-both' },
  OUT_OF_SCOPE:{ label: 'OOS',       cls: 'route-oos' },
}

function CitationBlock({ citations }) {
  const [open, setOpen] = useState(false)
  if (!citations || citations.length === 0) return null
  return (
    <div className="citations">
      <button className="cite-toggle" onClick={() => setOpen(o => !o)}>
        {open ? '▲ Hide' : '▼ Show'} {citations.length} citation{citations.length !== 1 ? 's' : ''}
      </button>
      {open && (
        <ol className="cite-list">
          {citations.map((c, i) => (
            <li key={i}>
              <span className={`cite-type ${c.type === 'sql' ? 'cite-sql' : 'cite-ngql'}`}>
                {c.type.toUpperCase()}
              </span>
              <pre className="cite-query">{c.query}</pre>
              {c.error
                ? <p className="cite-error">Error: {c.error}</p>
                : <p className="cite-rows">{c.rows.length} row(s) returned</p>
              }
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

function Message({ msg }) {
  if (msg.role === 'user') {
    return <div className="msg msg-user"><p>{msg.text}</p></div>
  }
  const route = ROUTE_BADGE[msg.route_tag] ?? { label: msg.route_tag, cls: 'route-sql' }
  return (
    <div className="msg msg-assistant">
      <span className={`route-badge ${route.cls}`}>{route.label}</span>
      <p style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</p>
      <CitationBlock citations={msg.citations} />
    </div>
  )
}

export default function Assistant({ warehouseId }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  const send = async () => {
    const q = input.trim()
    if (!q || loading) return
    setInput('')
    setMessages(m => [...m, { role: 'user', text: q }])
    setLoading(true)
    try {
      const res = await askQuestion(q, warehouseId)
      setMessages(m => [...m, {
        role: 'assistant',
        text: res.answer,
        citations: res.citations,
        route_tag: res.route_tag,
      }])
    } catch (e) {
      setMessages(m => [...m, { role: 'assistant', text: `Error: ${e.message}`, citations: [], route_tag: '' }])
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  return (
    <div className="surface assistant">
      <div className="chat-history">
        {messages.length === 0 && (
          <p className="muted chat-hint">
            Ask anything about your warehouse — e.g. "Why is BIN-PICKER-A failing so often?"
          </p>
        )}
        {messages.map((m, i) => <Message key={i} msg={m} />)}
        {loading && <div className="msg msg-assistant muted">Thinking…</div>}
      </div>

      <div className="chat-input-row">
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask a question… (Enter to send, Shift+Enter for newline)"
          rows={2}
          disabled={loading}
        />
        <button onClick={send} disabled={loading || !input.trim()}>
          {loading ? '…' : 'Send'}
        </button>
      </div>
    </div>
  )
}
