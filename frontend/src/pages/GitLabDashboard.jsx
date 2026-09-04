import { useCallback, useEffect, useState } from 'react'
import { gitlabApi } from '../gitlabApi.js'
import GitLabChatBot from '../components/GitLabChatBot.jsx'
import { ProjectContext } from '../components/gl/ui.jsx'
import ProjectsPanel from '../components/gl/ProjectsPanel.jsx'
import BranchesPanel from '../components/gl/BranchesPanel.jsx'
import MergeRequestsPanel from '../components/gl/MergeRequestsPanel.jsx'
import ReviewModal from '../components/gl/ReviewModal.jsx'
import ConfirmModal from '../components/ConfirmModal.jsx'

const TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'projects', label: 'Projects' },
  { key: 'branches', label: 'Branches' },
  { key: 'mrs', label: 'Merge Requests' },
]

function waitingSince(iso) {
  if (!iso) return 'unknown'
  const ms = Date.now() - new Date(iso).getTime()
  if (ms < 0) return 'just now'
  const s = Math.floor(ms / 1000)
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d}d ${h}h`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}
function waitingSeconds(iso) {
  if (!iso) return 0
  const ms = Date.now() - new Date(iso).getTime()
  return ms > 0 ? Math.floor(ms / 1000) : 0
}
function urgencyClass(secs) {
  if (secs >= 86400 * 2) return 'urgent'
  if (secs >= 86400) return 'warn'
  return 'ok'
}
function fmtDate(iso) {
  return iso ? new Date(iso).toLocaleString() : ''
}

function OverviewTab({ data, onOpenProject, onReview, onGate }) {
  const commits = (data?.commits ?? []).slice(0, 12)
  const mrs = (data?.pending_mrs ?? []).slice(0, 15)

  return (
    <div className="bb-overview">
      <section className="panel bb-wide pr-notif-panel">
        <div className="pr-notif-head">
          <h2>
            🔔 Merge Requests <span className="pr-bell">{mrs.length}</span>
          </h2>
          <span className="hint">Needs review — long-waiting MRs first. Approve / Merge are human-gated.</span>
        </div>

        {mrs.length === 0 && <p className="empty">Nothing waiting for review. 🎉</p>}

        <div className="pr-notif-list">
          {mrs.map((mr) => {
            const secs = waitingSeconds(mr.created_on || mr.created_at)
            const cls = urgencyClass(secs)
            return (
              <div key={`${mr.project}-${mr.iid}`} className={`pr-notif ${cls}`}>
                <span className="pr-dot" aria-hidden="true" />
                <span className="pr-notif-body">
                  <span className="pr-notif-title">!{mr.iid} · {mr.title}</span>
                  <span className="pr-notif-meta">
                    <span className="pr-notif-repo mono">📦 {mr.project}</span>
                    <span className="pr-notif-author">👤 {mr.author}</span>
                    <span className="mono">{mr.source_branch} → {mr.target_branch}</span>
                  </span>
                </span>
                <span className="pr-notif-wait">
                  <span className={`wait-chip ${cls}`}>{waitingSince(mr.created_on || mr.created_at)}</span>
                  <span className="gl-notif-actions">
                    <button className="btn btn-review btn-sm" onClick={() => onReview(mr)}>🔍 Review</button>
                    <button className="btn btn-primary btn-sm" onClick={() => onGate('approve', mr)}>Approve</button>
                    <button className="btn btn-danger btn-sm" onClick={() => onGate('merge', mr)}>Merge</button>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => onOpenProject(mr.project)}
                    >
                      Open ▸
                    </button>
                  </span>
                </span>
              </div>
            )
          })}
        </div>
      </section>

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
              <span className="commit-repo mono">📦 {c.repo}</span>
              <span className="commit-date">{c.date_display || fmtDate(c.date)}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

export default function GitLabDashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [chatOpen, setChatOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('overview')
  const [project, setProjectState] = useState('')
  const [projectLabel, setProjectLabel] = useState('')

  // overview-level review + gate modals
  const [review, setReview] = useState({ open: false, loading: false, error: '', verdict: null, title: '' })
  const [gate, setGate] = useState(null) // { type, mr }
  const [gateBusy, setGateBusy] = useState(false)
  const [gateNote, setGateNote] = useState('')

  const setProject = (id, label = '') => {
    setProjectState(id)
    setProjectLabel(label || id)
  }

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await gitlabApi.dashboard()
      if (res?.error) setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
      setData(res)
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

  function openProject(path) {
    setProject(path, path)
    setActiveTab('mrs')
  }

  async function runReview(mr) {
    setReview({ open: true, loading: true, error: '', verdict: null, title: `MR !${mr.iid} — ${mr.title}` })
    try {
      const res = await gitlabApi.reviewMr(mr.project, mr.iid)
      if (res?.error) setReview((r) => ({ ...r, loading: false, error: typeof res.error === 'string' ? res.error : JSON.stringify(res.error) }))
      else setReview((r) => ({ ...r, loading: false, verdict: res }))
    } catch (err) {
      setReview((r) => ({ ...r, loading: false, error: err.message }))
    }
  }

  async function runGate() {
    if (!gate) return
    setGateBusy(true)
    setGateNote('')
    try {
      const { type, mr } = gate
      const res =
        type === 'approve' ? await gitlabApi.approveMr(mr.project, mr.iid)
          : await gitlabApi.mergeMr(mr.project, mr.iid)
      if (res?.error) setGateNote(`⚠️ ${res.error}`)
      else if (res?.approved) setGateNote(`✅ MR !${mr.iid} approved.`)
      else if (res?.merged) setGateNote(`✅ MR !${mr.iid} merged.`)
      else setGateNote(`⚠️ ${res?.note || 'No confirmation returned.'}`)
      setGate(null)
      load()
    } catch (err) {
      setGateNote(`⚠️ ${err.message}`)
    } finally {
      setGateBusy(false)
    }
  }

  return (
    <ProjectContext.Provider value={{ project, projectLabel, setProject }}>
      <div className="bb-dashboard gl-dashboard">
        <header className="bb-topbar">
          <div>
            <h1>GitLab Command Center</h1>
            <p className="subtitle">Projects, merge requests, branches, commits — with an AI reviewer.</p>
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

        {activeTab !== 'overview' && activeTab !== 'projects' && (
          <div className="bb-repo-bar">
            <span className="repo-label">Active project:</span>
            <input
              className="strip-input"
              placeholder="project id or namespace/path (set via Projects tab)"
              value={project}
              onChange={(e) => setProject(e.target.value)}
            />
            <span className="repo-label">Used by Branches & Merge Requests.</span>
          </div>
        )}

        {error && (
          <div className="banner error-banner">
            ⚠️ {error} — is the backend running and are GITLAB_URL / GITLAB_TOKEN set?
          </div>
        )}
        {gateNote && <div className="bb-notice">{gateNote}</div>}

        {activeTab === 'overview' && (
          <>
            {s && (
              <section className="bb-cards">
                <div className="stat bb-total"><span className="num">{s.total_projects}</span><span>Projects</span></div>
                <div className="stat bb-open"><span className="num">{s.open_mrs}</span><span>Open MRs</span></div>
                <div className="stat bb-recent"><span className="num">{s.recent_commits}</span><span>Recent Commits</span></div>
              </section>
            )}
            {loading && !data && <div className="spinner">Fetching GitLab data…</div>}
            {data && !data.error && (
              <OverviewTab
                data={data}
                onOpenProject={openProject}
                onReview={runReview}
                onGate={(type, mr) => setGate({ type, mr })}
              />
            )}
          </>
        )}

        {activeTab === 'projects' && <ProjectsPanel />}
        {activeTab === 'branches' && <BranchesPanel />}
        {activeTab === 'mrs' && <MergeRequestsPanel />}

        <GitLabChatBot open={chatOpen} onToggle={() => setChatOpen((v) => !v)} />

        <ReviewModal
          open={review.open}
          title={review.title}
          loading={review.loading}
          error={review.error}
          verdict={review.verdict}
          onClose={() => setReview((r) => ({ ...r, open: false }))}
        />

        {gate && (
          <ConfirmModal
            open
            title={gate.type === 'approve' ? 'Approve Merge Request' : 'Merge Merge Request'}
            message={`${gate.type === 'approve' ? 'Approve' : 'Merge'} MR !${gate.mr.iid}? A human must confirm this.`}
            detail={`${gate.mr.project} → !${gate.mr.iid} ${gate.mr.title}`}
            confirmText={gate.type === 'approve' ? 'Approve' : 'Merge'}
            danger={gate.type === 'merge'}
            busy={gateBusy}
            onConfirm={runGate}
            onClose={() => !gateBusy && setGate(null)}
          />
        )}
      </div>
    </ProjectContext.Provider>
  )
}
