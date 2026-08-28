import { useCallback, useEffect, useState } from 'react'
import { bitbucketApi } from '../../bitbucketApi.js'
import { Panel, Empty, useRepo } from './ui.jsx'
import FormModal from './FormModal.jsx'
import ConfirmModal from '../ConfirmModal.jsx'

export default function ReposPanel() {
  const { repo: activeRepo, setRepo } = useRepo()
  const [repos, setRepos] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [detail, setDetail] = useState(null)
  const [busy, setBusy] = useState(false)

  // create / delete
  const [createOpen, setCreateOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await bitbucketApi.listRepos()
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
        setRepos([])
      } else {
        setRepos(res.values || [])
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function showDetail(slug) {
    setError('')
    setDetail(null)
    try {
      const res = await bitbucketApi.getRepo(slug)
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
      } else {
        setDetail(res)
      }
    } catch (err) {
      setError(err.message)
    }
  }

  async function createRepo(v) {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const res = await bitbucketApi.createRepo(v.repo_name, v.is_private === 'true', v.description)
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
      } else {
        setNotice(`✅ Repo "${v.repo_name}" created.`)
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
      const res = await bitbucketApi.deleteRepo(deleteTarget)
      setNotice(res?.deleted ? `🗑️ Repo "${deleteTarget}" deleted.` : `⚠️ ${res?.error || 'Could not delete.'}`)
      setDeleteTarget(null)
      if (activeRepo === deleteTarget) setRepo('')
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Panel title="Repositories" hint={`${repos.length} total`} wide>
      <div className="panel-toolbar">
        <button className="btn btn-primary btn-sm" onClick={() => setCreateOpen(true)}>
          + New Repo
        </button>
        <button className="btn btn-ghost btn-sm" onClick={load} disabled={loading}>
          {loading ? 'Loading…' : '⟳ Refresh'}
        </button>
      </div>

      {error && <p className="bb-notice">⚠️ {error}</p>}
      {notice && <p className="bb-notice">{notice}</p>}
      {repos.length === 0 && !loading && <Empty text="No repositories found." />}

      <div className="bb-table-wrap">
        <table className="bb-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Slug</th>
              <th>Language</th>
              <th>Private</th>
              <th>Updated</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {repos.map((r) => (
              <tr key={r.uuid || r.slug}>
                <td>
                  {r.name} {r.slug === activeRepo && <span className="active-repo">● active</span>}
                </td>
                <td className="mono">{r.slug}</td>
                <td>{r.language || '—'}</td>
                <td>{r.is_private ? 'Yes' : 'No'}</td>
                <td>{r.updated_on ? new Date(r.updated_on).toLocaleString() : '—'}</td>
                <td>
                  <div className="bb-actions">
                    <button className="btn btn-ghost btn-sm" onClick={() => showDetail(r.slug)}>
                      Details
                    </button>
                    <button className="btn btn-primary btn-sm" onClick={() => setRepo(r.slug)}>
                      Use in tabs
                    </button>
                    <button className="btn btn-danger btn-sm" onClick={() => setDeleteTarget(r.slug)}>
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {detail && (
        <Panel title={`Repo: ${detail.name || detail.full_name}`} wide>
          <div className="kv-grid">
            <K k="Name" v={detail.name} />
            <K k="Full name" v={detail.full_name} />
            <K k="Slug" v={detail.slug} />
            <K k="UUID" v={detail.uuid} />
            <K k="Language" v={detail.language} />
            <K k="Private" v={detail.is_private ? 'Yes' : 'No'} />
            <K k="Main branch" v={detail.mainbranch?.name} />
            <K k="Created" v={detail.created_on} />
            <K k="Updated" v={detail.updated_on} />
            <K k="Description" v={detail.description} />
          </div>
        </Panel>
      )}

      <FormModal
        open={createOpen}
        title="Create Repository"
        submitText="Create"
        busy={busy}
        error={error}
        fields={[
          { name: 'repo_name', label: 'Repository name', required: true },
          { name: 'description', label: 'Description', type: 'textarea' },
          { name: 'is_private', label: 'Visibility', type: 'select', default: 'true', options: ['true', 'false'] },
        ]}
        onSubmit={createRepo}
        onClose={() => setCreateOpen(false)}
      />

      <ConfirmModal
        open={!!deleteTarget}
        title="Delete Repository"
        message="This will permanently delete the repository. This is irreversible."
        detail={deleteTarget ? `Repository: ${deleteTarget}` : ''}
        confirmText="Delete"
        danger
        busy={busy}
        onConfirm={confirmDelete}
        onClose={() => !busy && setDeleteTarget(null)}
      />
    </Panel>
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
