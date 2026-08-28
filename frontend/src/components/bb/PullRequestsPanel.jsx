import { useCallback, useEffect, useState } from 'react'
import { bitbucketApi } from '../../bitbucketApi.js'
import { Panel, Empty, StatusChip, useRepo } from './ui.jsx'
import FormModal from './FormModal.jsx'
import ConfirmModal from '../ConfirmModal.jsx'

export default function PullRequestsPanel() {
  const { repo: activeRepo } = useRepo()
  const [state, setState] = useState('OPEN')
  const [prs, setPrs] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)

  // detail
  const [detail, setDetail] = useState(null)
  const [diff, setDiff] = useState(null)
  const [comments, setComments] = useState([])
  const [tasks, setTasks] = useState([])

  // modals
  const [createOpen, setCreateOpen] = useState(false)
  const [gated, setGated] = useState(null) // {type, pr}
  const [commentAddPr, setCommentAddPr] = useState(null)
  const [taskCreatePr, setTaskCreatePr] = useState(null)

  const hasRepo = Boolean(activeRepo)

  const load = useCallback(async () => {
    if (!activeRepo) return
    setLoading(true)
    setError('')
    try {
      const res = await bitbucketApi.listPrs(activeRepo, state)
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
        setPrs([])
      } else {
        setPrs(res.values || [])
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [activeRepo, state])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    setPrs([])
    setDetail(null)
  }, [activeRepo])

  async function showDetail(pr) {
    setError('')
    setDetail(pr)
    setDiff(null)
    setComments([])
    setTasks([])
    try {
      const [c, t] = await Promise.all([
        bitbucketApi.listPrComments(activeRepo, pr.id),
        bitbucketApi.listPrTasks(activeRepo, pr.id),
      ])
      setComments(c.values || (Array.isArray(c) ? c : []))
      setTasks(t.values || (Array.isArray(t) ? t : []))
    } catch (err) {
      setError(err.message)
    }
  }

  async function fetchDiff(pr) {
    setError('')
    try {
      const res = await bitbucketApi.getPrDiff(activeRepo, pr.id)
      setDiff(typeof res === 'string' ? res : JSON.stringify(res, null, 2))
    } catch (err) {
      setError(err.message)
    }
  }

  async function createPr(v) {
    if (!activeRepo) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const res = await bitbucketApi.createPr(activeRepo, v.title, v.source_branch, v.destination_branch, v.description)
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
      } else {
        setNotice(`✅ PR #${res.id} created: ${res.title}`)
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
    const { type, pr } = gated
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const res =
        type === 'approve'
          ? await bitbucketApi.approvePr(activeRepo, pr.id)
          : type === 'decline'
            ? await bitbucketApi.declinePr(activeRepo, pr.id)
            : await bitbucketApi.mergePr(activeRepo, pr.id)
      setNotice(res?.merged || res?.approved || res?.declined ? `✅ PR #${pr.id} ${type}d.` : `⚠️ ${res?.error || 'Could not act.'}`)
      setGated(null)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function addComment(v) {
    if (!commentAddPr || !activeRepo) return
    setBusy(true)
    setError('')
    try {
      const res = await bitbucketApi.addPrComment(activeRepo, commentAddPr.id, v.content)
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
      } else {
        setCommentAddPr(null)
        showDetail(commentAddPr)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function createTask(v) {
    if (!taskCreatePr || !activeRepo) return
    setBusy(true)
    setError('')
    try {
      const res = await bitbucketApi.createPrTask(activeRepo, taskCreatePr.id, v.content)
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
      } else {
        setTaskCreatePr(null)
        showDetail(taskCreatePr)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function toggleTask(task) {
    const newState = task.state === 'RESOLVED' ? 'UNRESOLVED' : 'RESOLVED'
    try {
      await bitbucketApi.updatePrTask(activeRepo, detail.id, task.id, '', newState)
      showDetail(detail)
    } catch (err) {
      setError(err.message)
    }
  }

  if (!hasRepo) {
    return (
      <Panel title="Pull Requests" hint="no repo selected">
        <p className="empty">Select a repository first (Repositories tab → Use in tabs).</p>
      </Panel>
    )
  }

  return (
    <>
      <Panel title="Pull Requests" hint={activeRepo} wide>
        <div className="panel-toolbar">
          <select className="strip-select" value={state} onChange={(e) => setState(e.target.value)}>
            <option value="OPEN">Open</option>
            <option value="MERGED">Merged</option>
            <option value="DECLINED">Declined</option>
            <option value="SUPERSEDED">Superseded</option>
            <option value="ALL">All</option>
          </select>
          {state === 'ALL' && (
            <button className="btn btn-ghost btn-sm" onClick={load}>
              Load
            </button>
          )}
          <button className="btn btn-primary btn-sm" onClick={() => setCreateOpen(true)}>
            + New PR
          </button>
        </div>

        {error && <p className="bb-notice">⚠️ {error}</p>}
        {notice && <p className="bb-notice">{notice}</p>}
        {prs.length === 0 && !loading && <Empty text="No pull requests in this state." />}

        <div className="bb-table-wrap">
          <table className="bb-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Title</th>
                <th>Author</th>
                <th>State</th>
                <th>Branches</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {prs.map((pr) => (
                <tr key={pr.id}>
                  <td className="mono">#{pr.id}</td>
                  <td className="msg-cell">{pr.title}</td>
                  <td>{pr.author?.display_name || pr.author?.nickname || ''}</td>
                  <td><StatusChip state={pr.state} /></td>
                  <td className="mono">
                    {pr.source?.branch?.name} → {pr.destination?.branch?.name}
                  </td>
                  <td>
                    <div className="bb-actions">
                      <button className="btn btn-ghost btn-sm" onClick={() => showDetail(pr)}>
                        View
                      </button>
                      <button className="btn btn-primary btn-sm" onClick={() => setGated({ type: 'approve', pr })}>
                        Approve
                      </button>
                      <button className="btn btn-warn btn-sm" onClick={() => setGated({ type: 'decline', pr })}>
                        Decline
                      </button>
                      <button className="btn btn-danger btn-sm" onClick={() => setGated({ type: 'merge', pr })}>
                        Merge
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {detail && (
        <Panel title={`PR #${detail.id}: ${detail.title}`} wide>
          <div className="kv-grid">
            <K k="Author" v={detail.author?.display_name || detail.author?.nickname} />
            <K k="State" v={detail.state} />
            <K k="Source" v={`${detail.source?.branch?.name}`} />
            <K k="Destination" v={`${detail.destination?.branch?.name}`} />
            <K k="Created" v={detail.created_on} />
            <K k="Description" v={detail.summary?.raw} />
          </div>

          <div className="panel-toolbar">
            <button className="btn btn-ghost btn-sm" onClick={() => fetchDiff(detail)}>
              Load Diff
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => setCommentAddPr(detail)}>
              + Comment
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => setTaskCreatePr(detail)}>
              + Task
            </button>
          </div>

          {diff && <pre className="code-block">{diff}</pre>}

          <h3 className="sub-h">Comments ({comments.length})</h3>
          {comments.length === 0 && <Empty text="No comments." />}
          <div className="mini-list">
            {comments.map((c) => (
              <div className="mini-item" key={c.id}>
                <span className="mini-who">{c.user?.display_name || 'User'}</span>
                <span className="mini-text">{c.content?.raw}</span>
              </div>
            ))}
          </div>

          <h3 className="sub-h">Tasks ({tasks.length})</h3>
          {tasks.length === 0 && <Empty text="No tasks." />}
          <div className="mini-list">
            {tasks.map((t) => (
              <div className="mini-item" key={t.id}>
                <button className="btn btn-sm btn-ghost" onClick={() => toggleTask(t)}>
                  {t.state === 'RESOLVED' ? '☑' : '☐'}
                </button>
                <span className="mini-text">{t.content?.raw}</span>
                <StatusChip state={t.state} />
              </div>
            ))}
          </div>
        </Panel>
      )}

      <FormModal
        open={createOpen}
        title="Create Pull Request"
        submitText="Create"
        busy={busy}
        error={error}
        fields={[
          { name: 'title', label: 'Title', required: true },
          { name: 'source_branch', label: 'Source branch (optional)' },
          { name: 'destination_branch', label: 'Destination branch (optional)' },
          { name: 'description', label: 'Description', type: 'textarea' },
        ]}
        onSubmit={createPr}
        onClose={() => setCreateOpen(false)}
      />

      {commentAddPr && (
        <FormModal
          open
          title={`Comment on PR #${commentAddPr.id}`}
          submitText="Post"
          busy={busy}
          error={error}
          fields={[{ name: 'content', label: 'Comment', type: 'textarea', required: true }]}
          onSubmit={addComment}
          onClose={() => setCommentAddPr(null)}
        />
      )}

      {taskCreatePr && (
        <FormModal
          open
          title={`New task on PR #${taskCreatePr.id}`}
          submitText="Add"
          busy={busy}
          error={error}
          fields={[{ name: 'content', label: 'Task', type: 'textarea', required: true }]}
          onSubmit={createTask}
          onClose={() => setTaskCreatePr(null)}
        />
      )}

      {gated && (
        <ConfirmModal
          open
          title={
            gated.type === 'approve'
              ? 'Approve Pull Request'
              : gated.type === 'decline'
                ? 'Decline Pull Request'
                : 'Merge Pull Request'
          }
          message={`${gated.type === 'approve' ? 'Approve' : gated.type === 'decline' ? 'Decline' : 'Merge'} PR #${gated.pr.id}?`}
          detail={`${activeRepo} → #${gated.pr.id} ${gated.pr.title}`}
          confirmText={gated.type === 'approve' ? 'Approve' : gated.type === 'decline' ? 'Decline' : 'Merge'}
          danger={gated.type !== 'approve'}
          busy={busy}
          onConfirm={runGated}
          onClose={() => !busy && setGated(null)}
        />
      )}
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
