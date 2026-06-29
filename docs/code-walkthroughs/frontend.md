# frontend/src/ — Code Walkthrough

> Source: `frontend/src/` (App.jsx, api.js, DiagnosesTable.jsx, Assistant.jsx, FeedbackView.jsx, App.css)
> Milestone: M9 · Last updated: 2026-06-27

## What it does

A single-page React app (Vite 5) that gives store managers three surfaces:
1. A ranked diagnoses grid with verdict badges and graph signal annotations.
2. A cited NL chat assistant.
3. A closed-loop feedback tracker.

---

## File map

```
frontend/src/
├── main.jsx            — ReactDOM.createRoot, imports App + CSS
├── App.jsx             — tab state, warehouse filter, route to surfaces
├── App.css             — all styles (dark theme, badges, pills, chat layout)
├── api.js              — axios client + 5 fetch functions
├── DiagnosesTable.jsx  — Surface 1
├── Assistant.jsx       — Surface 2
└── FeedbackView.jsx    — Surface 3
```

---

## `api.js` — shared Axios instance

```js
const http = axios.create({ baseURL: '/api' })
```

All requests go to `/api/*`. In dev, `vite.config.js` proxies these to
`http://localhost:8000` — no CORS headers needed, no env vars to set.

Five exported functions:
| Function | Endpoint |
|----------|----------|
| `fetchDiagnoses(wh, days)` | `GET /api/diagnoses` |
| `askQuestion(q, wh)` | `POST /api/ask` |
| `fetchFeedback(wh)` | `GET /api/feedback` |
| `createRecommendation(payload)` | `POST /api/feedback` |
| `advanceStatus(id, status)` | `PATCH /api/feedback/{id}/status` |

---

## `App.jsx` — shell

```jsx
const [tab, setTab] = useState('diagnoses')
const [warehouseId, setWarehouseId] = useState('WH-BLR-001')
```

`warehouseId` is a single input in the header that flows down as a prop to all
three surfaces. Changing it causes each surface to re-fetch with the new ID.
Tab switching is instant (no route change, no re-mount).

---

## Surface 1 — `DiagnosesTable.jsx`

### Fetch on mount and filter change
```jsx
useEffect(() => { load() }, [warehouseId, window])
```

### Verdict badges
```jsx
const VERDICT_LABELS = {
  PHANTOM_INVENTORY: { label: 'Phantom Inventory', cls: 'badge-phantom' },
  ...
}
<span className={`badge ${cls}`}>{label}</span>
```

CSS classes map to distinct dark-palette colours:
- `badge-phantom` → red tones
- `badge-genuine` → blue tones
- `badge-dual`    → purple tones
- `badge-ambiguous` → grey tones

### Graph signals
```jsx
function GraphSignals({ signals }) {
  if (!signals || Object.keys(signals).length === 0) return <span>—</span>
  return (
    <ul>
      {signals.picker_concentration && <li>🧍 Picker: PKR-BAD (100%)</li>}
      {signals.shared_grn && <li>📦 Shared GRN: GRN-999</li>}
      {signals.stocktake_done && <li>✅ Stocktake done</li>}
      {signals.atp_likely_zero && <li>⚠️ ATP likely 0</li>}
    </ul>
  )
}
```

Only signals that are present in the dict are rendered — empty dict shows `—`.

### Log Rec button
```jsx
await createRecommendation({ warehouse_id, bin, fsn, verdict, evidence_ref })
```

Calls `POST /api/feedback` with evidence_ref derived from distinct_fsns/distinct_bins.
A per-row loading state prevents double-clicks.

---

## Surface 2 — `Assistant.jsx`

### Message state
```jsx
const [messages, setMessages] = useState([])
// Each message: { role: 'user'|'assistant', text, citations, route_tag }
```

### Send on Enter
```jsx
const handleKey = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
}
```

Shift+Enter inserts a newline (standard textarea behaviour).

### Route badge
```jsx
const ROUTE_BADGE = {
  SQL_ONLY:    { label: 'SQL',       cls: 'route-sql' },
  GRAPH_ONLY:  { label: 'Graph',     cls: 'route-graph' },
  SQL_GRAPH:   { label: 'SQL+Graph', cls: 'route-both' },
  OUT_OF_SCOPE:{ label: 'OOS',       cls: 'route-oos' },
}
```

Displayed above each assistant message — tells the user whether Haiku routed to
SQL, graph, or both.

### Collapsible citations
```jsx
const [open, setOpen] = useState(false)
<button onClick={() => setOpen(o => !o)}>▼ Show N citations</button>
{open && <ol>...</ol>}
```

Hidden by default — keeps the chat readable. Each citation shows the exact
query the model ran and how many rows came back.

---

## Surface 3 — `FeedbackView.jsx`

### Status pills
```jsx
<span className={`status-pill status-${status}`}>{status}</span>
```

CSS: suggested=blue, acknowledged=yellow, executed=green, verified=bright green+border.

### Failures delta
```jsx
function FailuresDelta({ before, after, ceased }) {
  const color = ceased > 0 ? 'green' : ceased === 0 ? 'orange' : 'red'
  return <span style={{ color }}>{before} → {after} (−{ceased})</span>
}
```

Green = loop closed, orange = no change, red = worsened.

### Advance button
```jsx
const next = STATUS_NEXT[row.status]  // { suggested→acknowledged, ... }
await advanceStatus(row.id, next)
await load()   // re-fetch after advancing
```

---

## Technical decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Vite 5 (not CRA) | Vite | CRA deprecated; Vite is the 2024+ standard |
| Tab via `useState` | No React Router | 3 surfaces, no browser history needed |
| `warehouseId` in App state | Prop drilling | Simple; avoids Context or Redux for 3 components |
| Monolithic `App.css` | No CSS modules | Demo scale; all styles visible in one file |
| Vite `/api` proxy | `vite.config.js` | Dev CORS handled transparently; no env vars |
| Citations hidden by default | Toggle | Keeps chat readable; power-users can inspect |
| `failures_ceased` colour as inline style | Dynamic JS | Value-dependent colour; cleaner than 3 CSS classes |
