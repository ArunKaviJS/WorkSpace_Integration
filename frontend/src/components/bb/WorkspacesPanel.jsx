import { useCallback, useEffect, useState } from 'react'
import { bitbucketApi } from '../../bitbucketApi.js'
import { Panel, Empty } from './ui.jsx'

export default function WorkspacesPanel() {
  const [data, setData] = useState(null)
  const [workspace, setWorkspace] = useState('')
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await bitbucketApi.listWorkspaces()
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
        setData(null)
      } else {
        setData(res)
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

  async function fetchDetail(slug) {
    setError('')
    setDetail(null)
    try {
      const res = await bitbucketApi.getWorkspace(slug)
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
      } else {
        setDetail(res)
        setWorkspace(slug)
      }
    } catch (err) {
      setError(err.message)
    }
  }

  const values = data?.values || []

  return (
    <Panel title="Workspaces" hint="Workspaces you can access">
      {error && <p className="bb-notice">⚠️ {error}</p>}
      {loading && !data && <div className="spinner">Loading workspaces…</div>}

      {values.length === 0 && !loading && <Empty text="No workspaces returned." />}

      <div className="bb-table-wrap">
        <table className="bb-table">
          <thead>
            <tr>
              <th>Workspace</th>
              <th>Slug</th>
              <th>Admin</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {values.map((w) => {
              const ws = w.workspace || {}
              return (
                <tr key={ws.uuid || ws.slug}>
                  <td>{ws.name || ws.slug}</td>
                  <td className="mono">{ws.slug}</td>
                  <td>{w.administrator ? 'Yes' : 'No'}</td>
                  <td>
                    <button className="btn btn-ghost btn-sm" onClick={() => fetchDetail(ws.slug || ws.uuid)}>
                      Details
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {detail && (
        <Panel title={`Workspace: ${detail.name || workspace}`} wide>
          <div className="kv-grid">
            <K k="Name" v={detail.name} />
            <K k="Slug" v={detail.slug} />
            <K k="UUID" v={detail.uuid} />
            <K k="Private" v={detail.is_private ? 'Yes' : 'No'} />
            <K k="Type" v={detail.type} />
            <K k="Created" v={detail.created_on} />
          </div>
        </Panel>
      )}
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
