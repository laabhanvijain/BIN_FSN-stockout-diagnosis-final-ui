import axios from 'axios'

const http = axios.create({ baseURL: '/api' })

// ── Diagnoses ──────────────────────────────────────────────────────────────
export const fetchDiagnoses = (warehouseId, windowDays = 1) =>
  http.get('/diagnoses', {
    params: {
      ...(warehouseId && { warehouse_id: warehouseId }),
      window_days: windowDays,
    },
  }).then(r => r.data)

// ── Assistant ──────────────────────────────────────────────────────────────
export const askQuestion = (question, warehouseId) =>
  http.post('/ask', {
    question,
    ...(warehouseId && { warehouse_id: warehouseId }),
  }).then(r => r.data)

// ── Feedback ───────────────────────────────────────────────────────────────
export const fetchFeedback = (warehouseId) =>
  http.get('/feedback', {
    params: warehouseId ? { warehouse_id: warehouseId } : {},
  }).then(r => r.data)

export const createRecommendation = (payload) =>
  http.post('/feedback', payload).then(r => r.data)

export const advanceStatus = (id, status) =>
  http.patch(`/feedback/${id}/status`, { status }).then(r => r.data)
