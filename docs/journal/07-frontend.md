# 07 · Frontend (React)

> Milestone: M9. Detail: [../deliverables/LLD/08-frontend.md](../deliverables/LLD/08-frontend.md).

_Status: M9 done 2026-06-27._

---

## 2026-06-27 — M9 complete: React UI (3 surfaces)

### What was done

**Scaffold**: `frontend/package.json` (React 18, Vite 5, Axios), `vite.config.js`
(port 3000, `/api` proxy to `localhost:8000`), `index.html`, `src/main.jsx`.

**`api.js`**: Axios wrappers — `fetchDiagnoses`, `askQuestion`, `fetchFeedback`,
`createRecommendation`, `advanceStatus`. All use a shared Axios instance with
`baseURL='/api'` so the Vite proxy handles dev CORS transparently.

**`App.jsx`**: Tab bar (Diagnoses / Assistant / Feedback), warehouse ID input that
propagates to all surfaces, clean dark header. No React Router — tab is pure
`useState`.

**`DiagnosesTable.jsx`**: Ranked grid with colour-coded verdict badges, failures/orders
counts, recovery_pct, graph signal breakdown (picker, GRN, stocktake, ATP), window
selector, and a "Log Rec" button that calls `POST /api/feedback`.

**`Assistant.jsx`**: Chat UI — Enter to send, Shift+Enter for newlines, route badge
per message (SQL/Graph/SQL+Graph/OOS), collapsible citations showing query text and
row count for each tool call the model made.

**`FeedbackView.jsx`**: Lifecycle table — status pills, failures before→after with
colour-coded delta, "→ advance" button that calls `PATCH /api/feedback/{id}/status`
and re-fetches on success.

**`App.css`**: Single dark-theme stylesheet covering all surfaces — badges, pills,
chat layout, table alternating rows, citations expandable.

### Technical decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Vite (not CRA) | Vite 5 | CRA deprecated; Vite is the current standard |
| No React Router | `useState` tabs | 3 surfaces, no deep URLs; avoids routing overhead |
| Dark theme monolithic CSS | `App.css` | No build config overhead; correct for demo scale |
| Vite proxy for `/api` | `vite.config.js` | Dev CORS handled by proxy; no env vars needed |
| Citations collapsible | Toggle | Keeps chat readable; expand for deep inspection |

### Files created

- `frontend/package.json`, `vite.config.js`, `index.html`
- `frontend/src/main.jsx`, `App.jsx`, `App.css`, `api.js`
- `frontend/src/DiagnosesTable.jsx`, `Assistant.jsx`, `FeedbackView.jsx`

### Status: committed 2026-06-27

<!-- ## YYYY-MM-DD — <what happened> -->
