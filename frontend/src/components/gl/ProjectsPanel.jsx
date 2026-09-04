import { useCallback, useEffect, useState } from 'react'
import { gitlabApi } from '../../gitlabApi.js'
import { Panel, Empty, useProject } from './ui.jsx'
import FormModal from '../bb/FormModal.jsx'
import ConfirmModal from '../ConfirmModal.jsx'

export default function ProjectsPanel() {
  const { project: activeProject, setProject } = useProject()
  const [projects, setProjects] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [detail, setDetail] = useState(null)
  const [commits, setCommits] = useState([])

  // create / delete
  const [createOpen, setCreateOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await gitlabApi.listProjects(search)
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
        setProjects([])
      } else {
        setProjects(res.projects || [])
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [search])

  useEffect(() => {
    load()
  }, [load])

  async function showDetail(p) {
    setError('')
    setDetail(p)
    setCommits([])
    try {
      const res = await gitlabApi.projectCommits(p.path_with_namespace, '', 10)
      setCommits(res.commits || [])
    } catch (err) {
      setError(err.message)
    }
  }

  function useInTabs(p) {
    setProject(p.path_with_namespace, p.path_with_namespace)
  }

  async function createProject(v) {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const res = await gitlabApi.createProject({
        name: v.name,
        path: v.path || undefined,
        namespace_id: v.namespace_id ? Number(v.namespace_id) : undefined,
        visibility: v.visibility || 'private',
        description: v.description || undefined,
        initialize_with_readme: v.initialize_with_readme === 'true',
      })
      if (res && res.error) {
        // Friendly backend message (e.g. "You don't have permission … (403)")
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
      } else {
        setNotice(`✅ Project "${res.path_with_namespace || res.name}" created.`)
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
      const res = await gitlabApi.deleteProject(deleteTarget)
      if (res?.deleted) {
        setNotice(`🗑️ Project "${deleteTarget}" deleted.`)
        if (activeProject === deleteTarget) setProject('')
      } else {
        setError(res?.error ? String(res.error) : 'Could not delete this project.')
      }
      setDeleteTarget(null)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Panel title="Projects" hint={`${projects.length} shown`} wide>
      <div className="panel-toolbar">
        <button className="btn btn-primary btn-sm" onClick={() => setCreateOpen(true)}>
          + New Project
        </button>
        <input
          className="strip-input"
          placeholder="search projects…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && load()}
        />
        <button className="btn btn-ghost btn-sm" onClick={load} disabled={loading}>
          {loading ? 'Loading…' : '⟳ Refresh'}
        </button>
      </div>

      {error && <p className="bb-notice">⚠️ {error}</p>}
      {notice && <p className="bb-notice">{notice}</p>}
      {projects.length === 0 && !loading && <Empty text="No projects visible to this token." />}

      <div className="bb-table-wrap">
        <table className="bb-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Path</th>
              <th>Default branch</th>
              <th>Visibility</th>
              <th>Open issues</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {projects.map((p) => (
              <tr key={p.id}>
                <td>
                  {p.name}{' '}
                  {p.path_with_namespace === activeProject && (
                    <span className="active-repo">● active</span>
                  )}
                </td>
                <td className="mono">{p.path_with_namespace}</td>
                <td className="mono">{p.default_branch || '—'}</td>
                <td>{p.visibility}</td>
                <td>{p.open_issues_count ?? '—'}</td>
                <td>
                  <div className="bb-actions">
                    <button className="btn btn-ghost btn-sm" onClick={() => showDetail(p)}>
                      Details
                    </button>
                    <button className="btn btn-primary btn-sm" onClick={() => useInTabs(p)}>
                      Use in tabs
                    </button>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => setDeleteTarget(p.path_with_namespace)}
                    >
                      Delete
                    </button>
                    {p.web_url && (
                      <a className="btn btn-ghost btn-sm" href={p.web_url} target="_blank" rel="noreferrer">
                        Open ↗
                      </a>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {detail && (
        <Panel title={`Project: ${detail.name}`} wide>
          <div className="kv-grid">
            <K k="Path" v={detail.path_with_namespace} />
            <K k="ID" v={detail.id} />
            <K k="Default branch" v={detail.default_branch} />
            <K k="Visibility" v={detail.visibility} />
            <K k="Stars" v={detail.star_count} />
            <K k="Forks" v={detail.forks_count} />
            <K k="Last activity" v={detail.last_activity_at} />
            <K k="Description" v={detail.description} />
          </div>

          <h3 className="sub-h">Latest commits</h3>
          {commits.length === 0 && <Empty text="No commits." />}
          <div className="mini-list">
            {commits.map((c) => (
              <div className="mini-item" key={c.id}>
                <span className="mini-who mono">{c.short_id}</span>
                <span className="mini-text">{c.title}</span>
                <span className="commit-author">{c.author_name}</span>
              </div>
            ))}
          </div>
        </Panel>
      )}

      <FormModal
        open={createOpen}
        title="Create Project"
        submitText="Create"
        busy={busy}
        error={error}
        fields={[
          { name: 'name', label: 'Project name', required: true },
          { name: 'path', label: 'URL slug (optional — defaults from name)' },
          { name: 'namespace_id', label: 'Group namespace id (optional — blank = your namespace)', type: 'number' },
          { name: 'visibility', label: 'Visibility', type: 'select', default: 'private', options: ['private', 'internal', 'public'] },
          { name: 'description', label: 'Description', type: 'textarea' },
          { name: 'initialize_with_readme', label: 'Seed with README', type: 'select', default: 'true', options: ['true', 'false'] },
        ]}
        onSubmit={createProject}
        onClose={() => setCreateOpen(false)}
      />

      <ConfirmModal
        open={!!deleteTarget}
        title="Delete Project"
        message="This permanently deletes the project (repository) in GitLab. This is irreversible and needs Owner/admin rights on the project."
        detail={deleteTarget ? `Project: ${deleteTarget}` : ''}
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
