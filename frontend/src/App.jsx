import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import TaskCard from './components/TaskCard.jsx'
import TaskModal from './components/TaskModal.jsx'
import ChatBot from './components/ChatBot.jsx'

export default function App() {
  const [dash, setDash] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [chatOpen, setChatOpen] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setDash(await api.dashboard())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const s = dash?.summary

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>⚡ ClickUp AI Agent</h1>
          <p className="subtitle">Team command center — generated {dash?.generated_at ?? '…'}</p>
        </div>
        <button className="refresh-btn" onClick={load} disabled={loading}>
          {loading ? 'Loading…' : '⟳ Refresh'}
        </button>
      </header>

      {error && (
        <div className="banner error-banner">
          ⚠️ {error} — is the backend running? (<code>uvicorn server:app --port 8000</code>)
        </div>
      )}

      {s && (
        <section className="cards">
          <div className="stat total"><span className="num">{s.total}</span><span>Total</span></div>
          <div className="stat done"><span className="num">{s.completed}</span><span>Completed</span></div>
          <div className="stat pending"><span className="num">{s.pending}</span><span>Pending</span></div>
          <div className="stat overdue" onClick={() => document.getElementById('overdue-sec')?.scrollIntoView({ behavior: 'smooth' })}>
            <span className="num">{s.overdue}</span><span>Overdue</span>
          </div>
          <div className="stat due-soon"><span className="num">{s.due_soon_5min}</span><span>Due ≤ 5 min</span></div>
          <div className="stat soon24"><span className="num">{s.upcoming_24h}</span><span>Due in 24 h</span></div>
        </section>
      )}

      {loading && !dash && <div className="spinner">Fetching workspace data…</div>}

      {dash && (
        <div className="layout">
          <aside className="sidebar">
            <section id="overdue-sec" className="panel danger-panel sidebar-panel">
              <h2>🚨 Overdue Tasks <span className="hint">(click for details)</span></h2>
              {(dash.overdue_tasks?.length ?? 0) === 0 && (
                <p className="empty">Nothing overdue. Nice work! 🎉</p>
              )}
              <div className="task-list">
                {dash.overdue_tasks?.map((t) => (
                  <TaskCard key={t.id} task={t} variant="overdue-card" onClick={setSelected} />
                ))}
              </div>
            </section>
          </aside>

          <main className="grid">
            <section className="panel">
              <h2>⚠️ Due in 5 Minutes</h2>
              {(dash.due_soon_5min?.length ?? 0) === 0 && <p className="empty">No imminent deadlines.</p>}
              <div className="task-list">
                {dash.due_soon_5min?.map((t) => (
                  <TaskCard key={t.id} task={t} variant="soon-card" onClick={setSelected} />
                ))}
              </div>
            </section>

            <section className="panel">
              <h2>⏳ Due Next 24 Hours</h2>
              {(dash.upcoming_24h?.length ?? 0) === 0 && <p className="empty">Nothing due in the next day.</p>}
              <div className="task-list">
                {dash.upcoming_24h?.map((t) => (
                  <TaskCard key={t.id} task={t} variant="upcoming-card" onClick={setSelected} />
                ))}
              </div>
            </section>

            <section className="panel wide">
              <h2>👥 Per-Developer Breakdown</h2>
              <div className="dev-grid">
                {Object.entries(dash.per_developer || {}).map(([dev, st]) => (
                  <div key={dev} className="dev-card">
                    <h3>{dev}</h3>
                    <div className="dev-stats">
                      <span className="pill ok">✅ {st.completed.length}</span>
                      <span className="pill wait">⏳ {st.pending.length}</span>
                      <span className="pill bad">🚨 {st.overdue.length}</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </main>
        </div>
      )}

      <TaskModal task={selected} onClose={() => setSelected(null)} />
      <ChatBot open={chatOpen} onToggle={() => setChatOpen((v) => !v)} />
    </div>
  )
}
