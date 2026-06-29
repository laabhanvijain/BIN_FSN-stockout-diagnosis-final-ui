import { useState } from 'react'
import DiagnosesTable from './DiagnosesTable'
import Assistant from './Assistant'
import FeedbackView from './FeedbackView'

const TABS = [
  { id: 'diagnoses', label: '🔍 Diagnoses' },
  { id: 'assistant', label: '💬 Assistant' },
  { id: 'feedback',  label: '🔄 Feedback'  },
]

export default function App() {
  const [tab, setTab] = useState('diagnoses')
  const [warehouseId, setWarehouseId] = useState('WH-BLR-001')

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1>BIN-FSN Stockout Diagnosis</h1>
          <p className="header-sub">Dark store INF root-cause engine</p>
        </div>
        <div className="header-right">
          <label>
            Warehouse&nbsp;
            <input
              value={warehouseId}
              onChange={e => setWarehouseId(e.target.value)}
              placeholder="e.g. WH-BLR-001"
              className="wh-input"
            />
          </label>
        </div>
      </header>

      <nav className="tab-bar">
        {TABS.map(t => (
          <button
            key={t.id}
            className={`tab-btn ${tab === t.id ? 'tab-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main className="main-content">
        {tab === 'diagnoses' && <DiagnosesTable warehouseId={warehouseId} />}
        {tab === 'assistant' && <Assistant warehouseId={warehouseId} />}
        {tab === 'feedback'  && <FeedbackView warehouseId={warehouseId} />}
      </main>
    </div>
  )
}
