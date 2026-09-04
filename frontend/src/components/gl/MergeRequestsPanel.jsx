import { useCallback, useEffect, useState } from 'react'
import { gitlabApi } from '../../gitlabApi.js'
import { Panel, Empty, StatusChip, useProject } from './ui.jsx'
import FormModal from '../bb/FormModal.jsx'
import ConfirmModal from '../ConfirmModal.jsx'
import ReviewModal from './ReviewModal.jsx'

export default function MergeRequestsPanel() {
  const { project } = useProject()
  const [state, setState] = useState('opened')
  const [mrs, setMrs] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)

  // detail
  const [detail, setDetail] = useState(null)
  const [changes, setChanges] = useState(null)
  const [notes, setNotes] = useState([])

  // modals
  const [createOpen, setCreateOpen] = useState(false)
  const [gated, setGated] = useState(null) // { type, mr }
  const [noteMr, setNoteMr] = useState(null)

  // AI review
  const [review, setReview] = useState({ open: false, loading: false, error: '', verdict: null, title: '' })

  const load = useCallback(async () => {
    if (!project) return
    setLoading(true)
    setError('')
    try {
      const res = await gitlabApi.listMrs(project, state)
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
        setMrs([])
      } else {
        setMrs(res.merge_requests || [])
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [project, state])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    setMrs([])
    setDetail(null)
  }, [project])

  async function showDetail(mr) {
    setError('')
    setDetail(mr)
    setChanges(null)
    setNotes([])
    try {
      const [c, n] = await Promise.all([
        gitlabApi.getMrChanges(project, mr.iid),
        gitlabApi.listMrNotes(project, mr.iid),
      ])
      setChanges(c && !c.error ? c : null)
      setNotes(n?.notes || [])
    } catch (err) {
      setError(err.message)
    }
  }

  async function createMr(v) {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const res = await gitlabApi.createMr(project, v.source_branch, v.target_branch, v.title, v.description)
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
      } else {
        setNotice(`✅ MR !${res.iid} created: ${res.title}`)
        setCreateOpen(false)
        load()
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function runGated() {
    if (!gated) return
    const { type, mr } = gated
    setBusy(true)
    setError('')
    setNotice('')
    try {
      let res
      if (type === 'approve') res = await gitlabApi.approveMr(project, mr.iid)
      else if (type === 'merge') res = await gitlabApi.mergeMr(project, mr.iid)
      else res = await gitlabApi.closeMr(project, mr.iid)

      if (res?.error) setNotice(`⚠️ ${res.error}`)
      else if (res?.approved) setNotice(`✅ MR !${mr.iid} approved.`)
      else if (res?.merged) setNotice(`✅ MR !${mr.iid} merged.`)
      else if (res?.closed) setNotice(`✅ MR !${mr.iid} closed.`)
      else setNotice(`⚠️ ${res?.note || 'Action returned no confirmation.'}`)

      setGated(null)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function addNote(v) {
    if (!noteMr) return
    setBusy(true)
    setError('')
    try {
      const res = await gitlabApi.addMrNote(project, noteMr.iid, v.body)
      if (res?.error) setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
      else {
        setNoteMr(null)
        if (detail) showDetail(detail)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function runReview(mr) {
    setReview({ open: true, loading: true, error: '', verdict: null, title: `MR !${mr.iid} — ${mr.title}` })
    try {
      const res = await gitlabApi.reviewMr(project, mr.iid)
      if (res?.error) {
        setReview((r) => ({ ...r, loading: false, error: typeof res.error === 'string' ? res.error : JSON.stringify(res.error) }))
      } else {
        setReview((r) => ({ ...r, loading: false, verdict: res }))
      }
    } catch (err) {
      setReview((r) => ({ ...r, loading: false, error: err.message }))
    }
  }

  if (!project) {
    return (
      <Panel title="Merge Requests" hint="no project selected">
        <p className="empty">Pick a project first (Projects tab → Use in tabs).</p>
      </Panel>
    )
  }

  return (
    <>
      <Panel title="Merge Requests" hint={project} wide>
        <div className="panel-toolbar">
          <select className="strip-select" value={state} onChange={(e) => setState(e.target.value)}>
            <option value="opened">Opened</option>
            <option value="merged">Merged</option>
            <option value="closed">Closed</option>
            <option value="all">All</option>
          </select>
          <button className="btn btn-ghost btn-sm" onClick={load} disabled={loading}>
            {loading ? 'Loading…' : '⟳ Refresh'}
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => setCreateOpen(true)}>
            + New MR
          </button>
        </div>

        {error && <p className="bb-notice">⚠️ {error}</p>}
        {notice && <p className="bb-notice">{notice}</p>}
        {mrs.length === 0 && !loading && <Empty text="No merge requests in this state." />}

        <div className="bb-table-wrap">
          <table className="bb-table">
            <thead>
              <tr>
                <th>!IID</th>
                <th>Title</th>
                <th>Author</th>
                <th>State</th>
                <th>Branches</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {mrs.map((mr) => (
                <tr key={mr.iid}>
                  <td className="mono">!{mr.iid}</td>
                  <td className="msg-cell">
                    {mr.draft ? <span className="status-chip chip-amber">draft</span> : null} {mr.title}
                  </td>
                  <td>{mr.author}</td>
                  <td><StatusChip state={mr.state} /></td>
                  <td className="mono">{mr.source_branch} → {mr.target_branch}</td>
                  <td>
                    <div className="bb-actions">
                      <button className="btn btn-ghost btn-sm" onClick={() => showDetail(mr)}>View</button>
                      <button className="btn btn-review btn-sm" onClick={() => runReview(mr)}>🔍 AI Review</button>
                      <button className="btn btn-primary btn-sm" onClick={() => setGated({ type: 'approve', mr })}>Approve</button>
                      <button className="btn btn-danger btn-sm" onClick={() => setGated({ type: 'merge', mr })}>Merge</button>
                      <button className="btn btn-warn btn-sm" onClick={() => setGated({ type: 'close', mr })}>Close</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {detail && (
        <Panel title={`MR !${detail.iid}: ${detail.title}`} wide>
          <div className="kv-grid">
            <K k="Author" v={detail.author} />
            <K k="State" v={detail.state} />
            <K k="Source" v={detail.source_branch} />
            <K k="Target" v={detail.target_branch} />
            <K k="Merge status" v={detail.detailed_merge_status || detail.merge_status} />
            <K k="Conflicts" v={detail.has_conflicts ? 'Yes' : 'No'} />
            <K k="Created" v={detail.created_at} />
            <K k="Files changed" v={changes?.file_count} />
          </div>

          <div className="panel-toolbar">
            <button className="btn btn-review btn-sm" onClick={() => runReview(detail)}>🔍 Run AI Review</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setNoteMr(detail)}>+ Comment</button>
            {detail.web_url && (
              <a className="btn btn-ghost btn-sm" href={detail.web_url} target="_blank" rel="noreferrer">Open in GitLab ↗</a>
            )}
          </div>

          {changes?.files?.length > 0 && (
            <pre className="code-block">
              {changes.files
                .map((f) => `--- ${f.old_path}\n+++ ${f.new_path}\n${f.diff || ''}`)
                .join('\n')}
            </pre>
          )}

          <h3 className="sub-h">Notes ({notes.length})</h3>
          {notes.length === 0 && <Empty text="No comments." />}
          <div className="mini-list">
            {notes
              .filter((n) => !n.system)
              .map((n) => (
                <div className="mini-item" key={n.id}>
                  <span className="mini-who">{n.author}</span>
                  <span className="mini-text">{n.body}</span>
                </div>
              ))}
          </div>
        </Panel>
      )}

      <FormModal
        open={createOpen}
        title="Create Merge Request"
        submitText="Create"
        busy={busy}
        error={error}
        fields={[
          { name: 'title', label: 'Title', required: true },
          { name: 'source_branch', label: 'Source branch', required: true },
          { name: 'target_branch', label: 'Target branch', required: true },
          { name: 'description', label: 'Description', type: 'textarea' },
        ]}
        onSubmit={createMr}
        onClose={() => setCreateOpen(false)}
      />

      {noteMr && (
        <FormModal
          open
          title={`Comment on MR !${noteMr.iid}`}
          submitText="Post"
          busy={busy}
          error={error}
          fields={[{ name: 'body', label: 'Comment', type: 'textarea', required: true }]}
          onSubmit={addNote}
          onClose={() => setNoteMr(null)}
        />
      )}

      {gated && (
        <ConfirmModal
          open
          title={
            gated.type === 'approve' ? 'Approve Merge Request'
              : gated.type === 'merge' ? 'Merge Merge Request'
                : 'Close Merge Request'
          }
          message={`${gated.type === 'approve' ? 'Approve' : gated.type === 'merge' ? 'Merge' : 'Close'} MR !${gated.mr.iid}? A human must confirm this action.`}
          detail={`${project} → !${gated.mr.iid} ${gated.mr.title}`}
          confirmText={gated.type === 'approve' ? 'Approve' : gated.type === 'merge' ? 'Merge' : 'Close'}
          danger={gated.type !== 'approve'}
          busy={busy}
          onConfirm={runGated}
          onClose={() => !busy && setGated(null)}
        />
      )}

      <ReviewModal
        open={review.open}
        title={review.title}
        loading={review.loading}
        error={review.error}
        verdict={review.verdict}
        onClose={() => setReview((r) => ({ ...r, open: false }))}
      />
    </>
  )
}

function K({ k, v }) {
  return (
    <div className="kv-item">
      <span className="kv-key">{k}</span>
      <span className="kv-val">{v ?? '—'}</span>
    </div>
  )
}
