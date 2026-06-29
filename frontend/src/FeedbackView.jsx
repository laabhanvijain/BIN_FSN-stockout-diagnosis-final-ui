import { useState, useEffect } from 'react'
import { fetchFeedback, advanceStatus } from './api'

const STATUS_ORDER = ['suggested', 'acknowledged', 'executed', 'verified']

const STATUS_NEXT = {
  suggested: 'acknowledged',
  acknowledged: 'executed',
  executed: 'verified',
}

function StatusPill({ status }) {
  return <span className={`status-pill status-${status}`}>{status}</span>
}

function FailuresDelta({ before, after, ceased }) {
  if (before == null) return <span className="muted">—</span>
  if (after == null) return <span>{before} → ?</span>
  const color = ceased > 0 ? 'green' : ceased === 0 ? 'orange' : 'red'
  return (
    <span style={{ color }}>
      {before} → {after} ({ceased > 0 ? `−${ceased}` : ceased})
    </span>
  )
}

export default function FeedbackView({ warehouseId }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [advancing, setAdvancing] = useState({})

  const load = () => {
    setLoading(true)
    setError(null)
    fetchFeedback(warehouseId)
      .then(setRows)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [warehouseId])

  const advance = async (row) => {
    const next = STATUS_NEXT[row.status]
    if (!next) return
    setAdvancing(a => ({ ...a, [row.id]: true }))
    try {
      await advanceStatus(row.id, next)
      await load()
    } catch (e) {
      alert(`Failed: ${e.message}`)
    } finally {
      setAdvancing(a => ({ ...a, [row.id]: false }))
    }
  }

  return (
    <div className="surface">
      <div className="toolbar">
        <button onClick={load} disabled={loading}>
          {loading ? 'Loading…' : '↻ Refresh'}
        </button>
      </div>

      {error && <p className="error">Error: {error}</p>}

      {!loading && rows.length === 0 && !error && (
        <p className="muted">No recommendations logged yet. Log one from the Diagnoses tab.</p>
      )}

      {rows.length > 0 && (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>BIN</th>
                <th>FSN</th>
                <th>Verdict</th>
                <th>Action</th>
                <th>Status</th>
                <th>Failures (before → after)</th>
                <th>Suggested At</th>
                <th>Resolved At</th>
                <th>Advance</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.id} className={i % 2 === 0 ? 'row-even' : 'row-odd'}>
                  <td className="num">{r.id}</td>
                  <td><code>{r.bin}</code></td>
                  <td><code>{r.fsn}</code></td>
                  <td><span className="muted">{r.verdict}</span></td>
                  <td>{r.action}</td>
                  <td><StatusPill status={r.status} /></td>
                  <td>
                    <FailuresDelta
                      before={r.failures_before}
                      after={r.failures_after}
                      ceased={r.failures_ceased}
                    />
                  </td>
                  <td className="ts">{r.suggested_at?.slice(0, 16)}</td>
                  <td className="ts">{r.resolved_at?.slice(0, 16) ?? '—'}</td>
                  <td>
                    {STATUS_NEXT[r.status] ? (
                      <button
                        className="btn-advance"
                        onClick={() => advance(r)}
                        disabled={advancing[r.id]}
                      >
                        {advancing[r.id] ? '…' : `→ ${STATUS_NEXT[r.status]}`}
                      </button>
                    ) : (
                      <span className="muted">✓ done</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
