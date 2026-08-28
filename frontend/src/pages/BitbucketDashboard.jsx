import { useCallback, useEffect, useState } from 'react'
import { bitbucketApi } from '../bitbucketApi.js'
import BitbucketChatBot from '../components/BitbucketChatBot.jsx'
import { RepoContext } from '../components/bb/ui.jsx'
import WorkspacesPanel from '../components/bb/WorkspacesPanel.jsx'
import ReposPanel from '../components/bb/ReposPanel.jsx'
import FilesPanel from '../components/bb/FilesPanel.jsx'
import BranchesPanel from '../components/bb/BranchesPanel.jsx'
import PullRequestsPanel from '../components/bb/PullRequestsPanel.jsx'
import PipelinesPanel from '../components/bb/PipelinesPanel.jsx'
import DeploymentsPanel from '../components/bb/DeploymentsPanel.jsx'

const TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'workspaces', label: 'Workspaces' },
  { key: 'repos', label: 'Repositories' },
  { key: 'files', label: 'Files' },
  { key: 'branches', label: 'Branches' },
  { key: 'prs', label: 'Pull Requests' },
  { key: 'pipelines', label: 'Pipelines' },
  { key: 'deployments', label: 'Deployments' },
]

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

function urgencyClass(secs) {
  if (secs >= 86400 * 2) return 'urgent'
  if (secs >= 86400) return 'warn'
  return 'ok'
}

function waitingSeconds(createdOn) {
  if (!createdOn) return 0
  const created = new Date(createdOn)
  const ms = Date.now() - created.getTime()
  return ms > 0 ? Math.floor(ms / 1000) : 0
}

function OverviewTab({ data, onNavigate }) {
  const commits = (data?.commits ?? []).slice(0, 10)
  const prs = (data?.pending_prs ?? []).slice(0, 10)

  return (
    <div className="bb-overview">
      {/* ── Pull requests as interactive notifications ── */}
      <section className="panel bb-wide pr-notif-panel">
        <div className="pr-notif-head">
          <h2>
            🔔 Pull Requests <span className="pr-bell">{prs.length}</span>
          </h2>
          <span className="hint">Needs your review — newer & long-waiting PRs are highlighted first.</span>
        </div>

        {prs.length === 0 && <p className="empty">Nothing waiting for review. 🎉</p>}

        <div className="pr-notif-list">
          {prs.map((pr) => {
            const secs = waitingSeconds(pr.created_on)
            const cls = urgencyClass(secs)
            return (
              <button
                key={pr.id}
                className={`pr-notif ${cls}`}
                onClick={() => onNavigate('prs', pr.repo ? pr.repo.split('/')[1] : '')}
              >
                <span className="pr-dot" aria-hidden="true" />
                <span className="pr-notif-body">
                  <span className="pr-notif-title">{pr.title}</span>
                  <span className="pr-notif-meta">
                    <span className="pr-notif-repo mono">🏢 {pr.repo}</span>
                    <span className="pr-notif-author">👤 {pr.author}</span>
                  </span>
                </span>
                <span className="pr-notif-wait">
                  <span className={`wait-chip ${cls}`}>{waitingSince(pr.created_on)}</span>
                  <span className="pr-review-cta">Review →</span>
                </span>
              </button>
            )
          })}
        </div>
      </section>

      {/* ── Latest commits: scrollable (max 10) ── */}
      <section className="panel bb-wide">
        <h2>🚀 Latest Commits <span className="hint">({commits.length} of {data?.commits?.length ?? 0})</span></h2>
        {commits.length === 0 && <p className="empty">No commits found.</p>}
        <div className="commit-scroll">
          {commits.map((c, i) => (
            <div className="commit-row" key={c.hash || i}>
              <span className="commit-avatar">{c.author ? c.author.charAt(0).toUpperCase() : '?'}</span>
              <div className="commit-main">
                <span className="commit-msg">{c.message}</span>
                <span className="commit-author">{c.author}</span>
              </div>
              <span className="commit-repo mono">🏢 {c.repo}</span>
              <span className="commit-date">{c.date_display || fmtDate(c.date)}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

export default function BitbucketDashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [chatOpen, setChatOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('overview')
  const [repo, setRepo] = useState('')

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

  const onNavigate = (tab, repoSlug = '') => {
    if (repoSlug) setRepo(repoSlug)
    setActiveTab(tab)
  }

  return (
    <RepoContext.Provider value={{ repo, setRepo }}>
      <div className="bb-dashboard">
        <header className="bb-topbar">
          <div>
            <h1>Bitbucket Command Center</h1>
            <p className="subtitle">Workspaces, repos, pull requests, pipelines and deployments.</p>
          </div>
          <button className="refresh-btn" onClick={load} disabled={loading}>
            {loading ? 'Loading…' : '⟳ Refresh'}
          </button>
        </header>

        <nav className="bb-tabs">
          {TABS.map((t) => (
            <button
              key={t.key}
              className={`bb-tab ${activeTab === t.key ? 'active' : ''}`}
              onClick={() => setActiveTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </nav>

        {activeTab !== 'workspaces' && activeTab !== 'overview' && (
          <div className="bb-repo-bar">
            <span className="repo-label">Active repo:</span>
            <input
              className="strip-input"
              placeholder="repo slug (set via Repositories tab)"
              value={repo}
              onChange={(e) => setRepo(e.target.value)}
            />
            <span className="repo-label">Used by Files, Branches, PRs, Pipelines & Deployments.</span>
          </div>
        )}

        {error && (
          <div className="banner error-banner">
            ⚠️ {error} — is the backend running? (<code>uvicorn server:app --port 8000</code>)
          </div>
        )}

        {activeTab === 'overview' && (
          <>
            {s && (
              <section className="bb-cards">
                <div className="stat bb-total"><span className="num">{s.total_repos}</span><span>Repositories</span></div>
                <div className="stat bb-open"><span className="num">{s.open_prs}</span><span>Open PRs</span></div>
                <div className="stat bb-recent"><span className="num">{s.recent_commits}</span><span>Recent Commits</span></div>
              </section>
            )}

            {loading && !data && <div className="spinner">Fetching Bitbucket data…</div>}

            {data && <OverviewTab data={data} onNavigate={onNavigate} />}
          </>
        )}

        {activeTab === 'workspaces' && <WorkspacesPanel />}
        {activeTab === 'repos' && <ReposPanel />}
        {activeTab === 'files' && <FilesPanel />}
        {activeTab === 'branches' && <BranchesPanel />}
        {activeTab === 'prs' && <PullRequestsPanel />}
        {activeTab === 'pipelines' && <PipelinesPanel />}
        {activeTab === 'deployments' && <DeploymentsPanel />}

        <BitbucketChatBot open={chatOpen} onToggle={() => setChatOpen((v) => !v)} />
      </div>
    </RepoContext.Provider>
  )
}
