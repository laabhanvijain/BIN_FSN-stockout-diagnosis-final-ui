import { useState, useEffect } from 'react'
import { fetchDiagnoses, createRecommendation } from './api'

const VERDICT_LABELS = {
  PHANTOM_INVENTORY: { label: 'Phantom Inventory', cls: 'badge-phantom' },
  GENUINE_STOCKOUT:  { label: 'Genuine Stockout',  cls: 'badge-genuine' },
  DUAL:              { label: 'Dual',               cls: 'badge-dual' },
  AMBIGUOUS:         { label: 'Ambiguous',          cls: 'badge-ambiguous' },
}

function VerdictBadge({ verdict }) {
  const { label, cls } = VERDICT_LABELS[verdict] ?? { label: verdict, cls: 'badge-ambiguous' }
  return <span className={`badge ${cls}`}>{label}</span>
}

function GraphSignals({ signals }) {
  if (!signals || Object.keys(signals).length === 0) return <span className="muted">—</span>
  return (
    <ul className="signals-list">
      {signals.picker_concentration !== undefined && (
        <li>🧍 Picker: <strong>{signals.dominant_picker}</strong> ({(signals.picker_concentration * 100).toFixed(0)}%)</li>
      )}
      {signals.shared_grn && (
        <li>📦 Shared GRN: <strong>{signals.shared_grn}</strong> ({signals.fsn_count} FSNs)</li>
      )}
      {signals.stocktake_done && <li>✅ Stocktake already done</li>}
      {signals.atp_likely_zero && <li>⚠️ ATP likely 0</li>}
    </ul>
  )
}

export default function DiagnosesTable({ warehouseId }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [window, setWindow] = useState(1)
  const [logging, setLogging] = useState({})

  const load = () => {
    setLoading(true)
    setError(null)
    fetchDiagnoses(warehouseId, window)
      .then(setRows)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [warehouseId, window])

  const logRec = async (row) => {
    const key = `${row.bin}:${row.fsn}`
    setLogging(l => ({ ...l, [key]: true }))
    try {
      await createRecommendation({
        warehouse_id: row.warehouse_id,
        bin: row.bin,
        fsn: row.fsn,
        verdict: row.verdict,
        evidence_ref: `distinct_fsns=${row.distinct_fsns}, distinct_bins=${row.distinct_bins}`,
      })
      alert(`Recommendation logged for ${row.bin} / ${row.fsn}`)
    } catch (e) {
      alert(`Failed: ${e.message}`)
    } finally {
      setLogging(l => ({ ...l, [key]: false }))
    }
  }

  return (
    <div className="surface">
      <div className="toolbar">
        <label>
          Window:&nbsp;
          <select value={window} onChange={e => setWindow(Number(e.target.value))}>
            {[1, 3, 7, 14, 30].map(d => <option key={d} value={d}>{d}d</option>)}
          </select>
        </label>
        <button onClick={load} disabled={loading}>
          {loading ? 'Loading…' : '↻ Refresh'}
        </button>
      </div>

      {error && <p className="error">Error: {error}</p>}

      {!loading && rows.length === 0 && !error && (
        <p className="muted">No active INF clusters in the selected window.</p>
      )}

      {rows.length > 0 && (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>BIN</th>
                <th>FSN</th>
                <th>Verdict</th>
                <th>Failures</th>
                <th>Orders Impacted</th>
                <th>Distinct FSNs</th>
                <th>Distinct BINs</th>
                <th>Recovery %</th>
                <th>Graph Signals</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const key = `${r.bin}:${r.fsn}`
                return (
                  <tr key={i} className={i % 2 === 0 ? 'row-even' : 'row-odd'}>
                    <td><code>{r.bin}</code></td>
                    <td><code>{r.fsn}</code></td>
                    <td><VerdictBadge verdict={r.verdict} /></td>
                    <td className="num">{r.failures}</td>
                    <td className="num">{r.orders_impacted}</td>
                    <td className="num">{r.distinct_fsns}</td>
                    <td className="num">{r.distinct_bins}</td>
                    <td className="num">{r.recovery_pct}%</td>
                    <td><GraphSignals signals={r.graph_signals} /></td>
                    <td>
                      <button
                        className="btn-log"
                        onClick={() => logRec(r)}
                        disabled={logging[key]}
                      >
                        {logging[key] ? '…' : 'Log Rec'}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
