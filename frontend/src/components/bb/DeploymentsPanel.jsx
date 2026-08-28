import { useCallback, useEffect, useState } from 'react'
import { bitbucketApi } from '../../bitbucketApi.js'
import { Panel, Empty, StatusChip, useRepo } from './ui.jsx'
import FormModal from './FormModal.jsx'
import ConfirmModal from '../ConfirmModal.jsx'

export default function DeploymentsPanel() {
  const { repo: activeRepo } = useRepo()
  const [envs, setEnvs] = useState([])
  const [deployments, setDeployments] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)

  const [createOpen, setCreateOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [updateTarget, setUpdateTarget] = useState(null)
  const [envDetail, setEnvDetail] = useState(null)

  const load = useCallback(async () => {
    if (!activeRepo) return
    setLoading(true)
    setError('')
    try {
      const [eRes, dRes] = await Promise.all([
        bitbucketApi.listEnvironments(activeRepo),
        bitbucketApi.listDeployments(activeRepo),
      ])
      setEnvs(eRes.values || (Array.isArray(eRes) ? eRes : []))
      setDeployments(dRes.values || (Array.isArray(dRes) ? dRes : []))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [activeRepo])

  useEffect(() => {
    setEnvs([])
    setDeployments([])
    setEnvDetail(null)
    if (activeRepo) load()
  }, [activeRepo, load])

  async function createEnv(v) {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const res = await bitbucketApi.createEnvironment(activeRepo, v.name, v.environment_type)
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
      } else {
        setNotice(`✅ Environment "${v.name}" created.`)
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
      const res = await bitbucketApi.deleteEnvironment(activeRepo, deleteTarget.uuid)
      setNotice(res?.deleted ? `🗑️ Environment deleted.` : `⚠️ ${res?.error || 'Could not delete.'}`)
      setDeleteTarget(null)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function updateEnv(v) {
    if (!updateTarget) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const update = { name: v.name }
      const res = await bitbucketApi.updateEnvironment(activeRepo, updateTarget.uuid, update)
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
      } else {
        setNotice('✅ Environment updated.')
        setUpdateTarget(null)
        load()
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function showEnv(env) {
    setError('')
    setEnvDetail(null)
    try {
      const res = await bitbucketApi.getEnvironment(activeRepo, env.uuid)
      setEnvDetail(res && !res.error ? res : null)
    } catch (err) {
      setError(err.message)
    }
  }

  if (!activeRepo) {
    return (
      <Panel title="Deployments & Environments" hint="no repo selected">
        <p className="empty">Select a repository first (Repositories tab → Use in tabs).</p>
      </Panel>
    )
  }

  return (
    <>
      <Panel title="Environments" hint={activeRepo} wide>
        <div className="panel-toolbar">
          <button className="btn btn-primary btn-sm" onClick={() => setCreateOpen(true)}>
            + New Environment
          </button>
          <button className="btn btn-ghost btn-sm" onClick={load} disabled={loading}>
            {loading ? 'Loading…' : '⟳ Refresh'}
          </button>
        </div>

        {error && <p className="bb-notice">⚠️ {error}</p>}
        {notice && <p className="bb-notice">{notice}</p>}
        {envs.length === 0 && !loading && <Empty text="No environments configured." />}

        <div className="bb-table-wrap">
          <table className="bb-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>UUID</th>
                <th>Type</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {envs.map((e) => (
                <tr key={e.uuid}>
                  <td>{e.name}</td>
                  <td className="mono">{e.uuid}</td>
                  <td>{e.environment_type || '—'}</td>
                  <td>
                    <div className="bb-actions">
                      <button className="btn btn-ghost btn-sm" onClick={() => showEnv(e)}>
                        Details
                      </button>
                      <button className="btn btn-ghost btn-sm" onClick={() => setUpdateTarget(e)}>
                        Rename
                      </button>
                      <button className="btn btn-danger btn-sm" onClick={() => setDeleteTarget(e)}>
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {envDetail && (
        <Panel title={`Environment: ${envDetail.name}`} wide>
          <div className="kv-grid">
            <K k="Name" v={envDetail.name} />
            <K k="UUID" v={envDetail.uuid} />
            <K k="Type" v={envDetail.environment_type} />
            <K k="Type rank" v={envDetail.environment_type_rank} />
          </div>
        </Panel>
      )}

      <Panel title="Deployments" hint={`${deployments.length} total`} wide>
        <div className="bb-table-wrap">
          <table className="bb-table">
            <thead>
              <tr>
                <th>Deployment</th>
                <th>Environment</th>
                <th>State</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {deployments.map((d) => (
                <tr key={d.uuid}>
                  <td className="mono">{d.uuid?.slice(0, 8)}</td>
                  <td>{d.environment?.name || '—'}</td>
                  <td><StatusChip state={d.state?.name} /></td>
                  <td>{d.created_on ? new Date(d.created_on).toLocaleString() : '—'}</td>
                </tr>
              ))}
              {deployments.length === 0 && (
                <tr>
                  <td colSpan={4} className="empty">
                    No deployments yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>

      <FormModal
        open={createOpen}
        title="Create Environment"
        submitText="Create"
        busy={busy}
        error={error}
        fields={[
          { name: 'name', label: 'Environment name', required: true },
          { name: 'environment_type', label: 'Type', type: 'select', default: 'Production', options: ['Production', 'Staging', 'Test', 'Development'] },
        ]}
        onSubmit={createEnv}
        onClose={() => setCreateOpen(false)}
      />

      {updateTarget && (
        <FormModal
          open
          title={`Rename Environment: ${updateTarget.name}`}
          submitText="Save"
          busy={busy}
          error={error}
          fields={[{ name: 'name', label: 'New name', required: true, default: updateTarget.name }]}
          onSubmit={updateEnv}
          onClose={() => setUpdateTarget(null)}
        />
      )}

      <ConfirmModal
        open={!!deleteTarget}
        title="Delete Environment"
        message="This will permanently delete the environment and its deployments."
        detail={deleteTarget ? `Environment: ${deleteTarget.name} (${deleteTarget.uuid})` : ''}
        confirmText="Delete"
        danger
        busy={busy}
        onConfirm={confirmDelete}
        onClose={() => !busy && setDeleteTarget(null)}
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
