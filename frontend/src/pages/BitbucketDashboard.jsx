import { useCallback, useEffect, useState } from 'react'
import { bitbucketApi } from '../bitbucketApi.js'
import ConfirmModal from '../components/ConfirmModal.jsx'
import BitbucketChatBot from '../components/BitbucketChatBot.jsx'

function waitingSince(createdOn) {
  if (!createdOn) return 'unknown'
  const created = new Date(createdOn)
  const ms = Date.now() - created.getTime()
  if (ms < 0) return 'just now'
  const s = Math.floor(ms / 1000)
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d}d ${h}h`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

function fmtDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString()
}

export default function BitbucketDashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Confirmation modal state for human-gated PR actions
  const [pendingAction, setPendingAction] = useState(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)
  const [chatOpen, setChatOpen] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await bitbucketApi.dashboard())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const s = data?.summary

  async function runAction() {
    if (!pendingAction) return
    setBusy(true)
    setNotice(null)
    try {
      const { type, repo_slug, pr_id } = pendingAction
      const result =
        type === 'approve'
          ? await bitbucketApi.approvePr(repo_slug, pr_id)
          : type === 'decline'
            ? await bitbucketApi.declinePr(repo_slug, pr_id)
            : await bitbucketApi.mergePr(repo_slug, pr_id)
      if (result && result.needs_confirmation) {
        setNotice(`⚠️ Confirmation required: ${result.reason}`)
      } else if (result && result.error) {
        setNotice(`⚠️ ${result.error}`)
      } else {
        setNotice(`✅ PR #${pr_id} ${type}d successfully.`)
      }
      setPendingAction(null)
      load()
    } catch (err) {
      setNotice(`⚠️ ${err.message}`)
      setPendingAction(null)
    } finally {
      setBusy(false)
    }
  }

  const prActionMeta = (type) => ({
    title: type === 'approve' ? 'Approve Pull Request' : type === 'decline' ? 'Decline Pull Request' : 'Merge Pull Request',
    message:
      type === 'approve'
        ? 'Approve this pull request?'
        : type === 'decline'
          ? 'Decline this pull request?'
          : 'Merge (fulfill) this pull request?',
    confirmText: type === 'approve' ? 'Approve' : type === 'decline' ? 'Decline' : 'Merge',
  })

  return (
    <div className="bb-dashboard">
      <header className="bb-topbar">
        <div>
          <h1>Bitbucket Command Center</h1>
          <p className="subtitle">Repos, commits and pull requests — one place.</p>
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

      {notice && <div className="bb-notice">{notice}</div>}

      {s && (
        <section className="bb-cards">
          <div className="stat bb-total"><span className="num">{s.total_repos}</span><span>Repositories</span></div>
          <div className="stat bb-open"><span className="num">{s.open_prs}</span><span>Open PRs</span></div>
          <div className="stat bb-recent"><span className="num">{s.recent_commits}</span><span>Recent Commits</span></div>
        </section>
      )}

      {loading && !data && <div className="spinner">Fetching Bitbucket data…</div>}

      {data && (
        <div className="bb-grid">
          {/* Latest 10 Commits */}
          <section className="panel bb-wide">
            <h2>🚀 Latest Commits</h2>
            {(data.commits?.length ?? 0) === 0 && <p className="empty">No commits found.</p>}
            <div className="bb-table-wrap">
              <table className="bb-table">
                <thead>
                  <tr>
                    <th>Repository</th>
                    <th>Author</th>
                    <th>Message</th>
                    <th>Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  {data.commits?.map((c, i) => (
                    <tr key={c.hash || i}>
                      <td className="mono">{c.repo}</td>
                      <td>{c.author}</td>
                      <td className="msg-cell">{c.message}</td>
                      <td>{c.date_display || fmtDate(c.date)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Pending PRs */}
          <section className="panel bb-wide">
            <h2>⏳ Pending Pull Requests ({data.pending_prs?.length ?? 0})</h2>
            {(data.pending_prs?.length ?? 0) === 0 && <p className="empty">Nothing waiting for review. 🎉</p>}
            <div className="bb-table-wrap">
              <table className="bb-table">
                <thead>
                  <tr>
                    <th>Repository</th>
                    <th>Title</th>
                    <th>Author</th>
                    <th>Waiting</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.pending_prs?.map((pr) => (
                    <tr key={pr.id}>
                      <td className="mono">{pr.repo}</td>
                      <td className="msg-cell">{pr.title}</td>
                      <td>{pr.author}</td>
                      <td>
                        <span className="wait-chip">{waitingSince(pr.created_on)}</span>
                      </td>
                      <td>
                        <div className="bb-actions">
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={() => setPendingAction({ type: 'approve', repo_slug: pr.repo.split('/')[1], pr_id: pr.id })}
                          >
                            Approve
                          </button>
                          <button
                            className="btn btn-warn btn-sm"
                            onClick={() => setPendingAction({ type: 'decline', repo_slug: pr.repo.split('/')[1], pr_id: pr.id })}
                          >
                            Decline
                          </button>
                          <button
                            className="btn btn-danger btn-sm"
                            onClick={() => setPendingAction({ type: 'merge', repo_slug: pr.repo.split('/')[1], pr_id: pr.id })}
                          >
                            Merge
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}

      <ConfirmModal
        open={!!pendingAction}
        {...prActionMeta(pendingAction?.type)}
        detail={
          pendingAction
            ? `PR #${pendingAction.pr_id} in ${pendingAction.repo_slug}`
            : ''
        }
        danger={pendingAction?.type === 'merge' || pendingAction?.type === 'decline'}
        busy={busy}
        onConfirm={runAction}
        onClose={() => !busy && setPendingAction(null)}
      />

      <BitbucketChatBot open={chatOpen} onToggle={() => setChatOpen((v) => !v)} />
    </div>
  )
}
