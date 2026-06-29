# LLD 08 · Frontend

> Status: **DONE** (M9 · 2026-06-27). Source: `frontend/src/`.

---

## Stack & structure

| Tool | Version | Why |
|------|---------|-----|
| Vite | 5.x | Fast HMR, ESM-first, minimal config |
| React | 18.x | Component model, hooks |
| Axios | 1.7 | HTTP client with easy baseURL and param handling |

```
frontend/
├── index.html
├── package.json
├── vite.config.js          ← /api proxy to localhost:8000
└── src/
    ├── main.jsx            ← ReactDOM.createRoot entry
    ├── App.jsx             ← tab bar, warehouse filter, route to surfaces
    ├── App.css             ← dark theme, all component styles
    ├── api.js              ← axios wrappers for all 3 endpoints
    ├── DiagnosesTable.jsx  ← Surface 1: verdict grid + graph signals + Log Rec button
    ├── Assistant.jsx       ← Surface 2: chat UI + citations expandable
    └── FeedbackView.jsx    ← Surface 3: lifecycle table + → advance button
```

---

## Surface 1 — DiagnosesTable

- Calls `GET /api/diagnoses?warehouse_id=&window_days=` on mount and on filter change.
- Renders a scrollable table with verdict badges (colour-coded by type), failures/orders counts,
  `recovery_pct`, and graph signals (picker concentration, shared GRN, stocktake, ATP).
- **Log Rec** button calls `POST /api/feedback` to create a recommendation from that row.
- Window selector (1/3/7/14/30d) triggers a re-fetch.

## Surface 2 — Assistant

- Textarea + Send button; Enter sends, Shift+Enter inserts newline.
- Each assistant message shows a **route badge** (SQL / Graph / SQL+Graph / OOS)
  derived from `route_tag` in the API response.
- Citations are hidden by default behind a collapsible toggle — shows query text,
  row count, and any error for each tool call.

## Surface 3 — FeedbackView

- Calls `GET /api/feedback?warehouse_id=` on mount.
- Shows lifecycle status as colour-coded pills (suggested=blue, acknowledged=yellow,
  executed=green, verified=bright green with border).
- **Failures delta** column: `before → after (−ceased)` in green/orange/red based on direction.
- **→ advance** button calls `PATCH /api/feedback/{id}/status` with the next lifecycle step.

---

## Vite proxy

```js
proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } }
```

All `/api/*` requests in dev are proxied to the FastAPI backend — no CORS config
needed during development.

---

## Key Technical Decisions

| Decision | Choice | Alternatives | Why |
|----------|--------|-------------|-----|
| Vite (no CRA) | Vite 5 | Create React App (deprecated) | CRA is unmaintained; Vite is the current standard |
| No React Router | Tab state via `useState` | React Router | 3 surfaces, no deep URLs needed; avoids routing overhead |
| Dark theme in single CSS | Monolithic `App.css` | CSS modules / Tailwind | Simpler for demo; no build config needed |
| Axios with `/api` baseURL | Axios + Vite proxy | Fetch + full URL | Clean relative URLs; proxy handles dev CORS |
| Citations collapsible | Toggle show/hide | Always visible | Keeps chat readable; power-users can expand |
| `failures_ceased` colour coding | JS inline `style={{ color }}` | CSS classes | Dynamic value at render time; cleaner than 3 conditional classes |
