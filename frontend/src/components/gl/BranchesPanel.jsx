import { useCallback, useEffect, useState } from 'react'
import { gitlabApi } from '../../gitlabApi.js'
import { Panel, Empty, useProject } from './ui.jsx'
import FormModal from '../bb/FormModal.jsx'
import ConfirmModal from '../ConfirmModal.jsx'

export default function BranchesPanel() {
  const { project } = useProject()
  const [branches, setBranches] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const load = useCallback(async () => {
    if (!project) return
    setLoading(true)
    setError('')
    try {
      const res = await gitlabApi.listBranches(project)
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
        setBranches([])
      } else {
        setBranches(res.branches || [])
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [project])

  useEffect(() => {
    load()
  }, [load])

  async function createBranch(v) {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const res = await gitlabApi.createBranch(project, v.branch, v.ref)
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
      } else {
        setNotice(`✅ Branch "${res.name}" created.`)
        setCreateOpen(false)
        load()
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const res = await gitlabApi.deleteBranch(project, deleteTarget)
      setNotice(res?.deleted ? `🗑️ Branch "${deleteTarget}" deleted.` : `⚠️ ${res?.error || res?.note || 'Could not delete.'}`)
      setDeleteTarget(null)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!project) {
    return (
      <Panel title="Branches" hint="no project selected">
        <p className="empty">Pick a project first (Projects tab → Use in tabs).</p>
      </Panel>
    )
  }

  return (
    <Panel title="Branches" hint={project} wide>
      <div className="panel-toolbar">
        <button className="btn btn-primary btn-sm" onClick={() => setCreateOpen(true)}>
          + New Branch
        </button>
        <button className="btn btn-ghost btn-sm" onClick={load} disabled={loading}>
          {loading ? 'Loading…' : '⟳ Refresh'}
        </button>
      </div>

      {error && <p className="bb-notice">⚠️ {error}</p>}
      {notice && <p className="bb-notice">{notice}</p>}
      {branches.length === 0 && !loading && <Empty text="No branches." />}

      <div className="bb-table-wrap">
        <table className="bb-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Head</th>
              <th>Last commit</th>
              <th>Flags</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {branches.map((b) => (
              <tr key={b.name}>
                <td className="mono">{b.name}</td>
                <td className="mono">{b.commit?.short_id}</td>
                <td className="msg-cell">{b.commit?.title}</td>
                <td>
                  {b.default && <span className="status-chip chip-blue">default</span>}{' '}
                  {b.protected && <span className="status-chip chip-amber">protected</span>}{' '}
                  {b.merged && <span className="status-chip chip-green">merged</span>}
                </td>
                <td>
                  <div className="bb-actions">
                    <button
                      className="btn btn-danger btn-sm"
                      disabled={b.default || b.protected}
                      onClick={() => setDeleteTarget(b.name)}
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <FormModal
        open={createOpen}
        title="Create Branch"
        submitText="Create"
        busy={busy}
        error={error}
        fields={[
          { name: 'branch', label: 'New branch name', required: true },
          { name: 'ref', label: 'From ref (branch / tag / SHA — blank = default)' },
        ]}
        onSubmit={createBranch}
        onClose={() => setCreateOpen(false)}
      />

      <ConfirmModal
        open={!!deleteTarget}
        title="Delete Branch"
        message="This will permanently delete the branch."
        detail={deleteTarget ? `${project} → ${deleteTarget}` : ''}
        confirmText="Delete"
        danger
        busy={busy}
        onConfirm={confirmDelete}
        onClose={() => !busy && setDeleteTarget(null)}
      />
    </Panel>
  )
}
