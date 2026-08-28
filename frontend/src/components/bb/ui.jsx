import { createContext, useContext } from 'react'

// Shares the currently selected repository (slug) across all Bitbucket tabs
// so the user only picks a repo once per session.
export const RepoContext = createContext({ repo: '', setRepo: () => {} })

export function useRepo() {
  return useContext(RepoContext)
}

export function Panel({ title, hint, children, wide }) {
  return (
    <section className={`panel ${wide ? 'wide' : ''}`}>
      <h2>
        {title}
        {hint ? <span className="hint"> {hint}</span> : null}
      </h2>
      {children}
    </section>
  )
}

export function Empty({ text }) {
  return <p className="empty">{text}</p>
}

export function StatusChip({ state }) {
  const s = String(state || '').toUpperCase()
  const cls =
    s.includes('SUCCESSFUL') || s === 'COMPLETED' || s === 'RESOLVED' ? 'chip-green'
    : s.includes('FAILED') || s === 'ERROR' || s === 'DECLINED' || s === 'CANCELLED' ? 'chip-red'
    : s.includes('RUNNING') || s === 'OPEN' || s === 'PENDING' || s === 'INPROGRESS' ? 'chip-amber'
    : 'chip-blue'
  return <span className={`status-chip ${cls}`}>{s || '—'}</span>
}
