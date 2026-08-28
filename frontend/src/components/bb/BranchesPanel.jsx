import { useState } from 'react'
import { bitbucketApi } from '../../bitbucketApi.js'
import { Panel, useRepo } from './ui.jsx'
import FormModal from './FormModal.jsx'

export default function BranchesPanel() {
  const { repo: activeRepo } = useRepo()
  const [branchInfo, setBranchInfo] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [getOpen, setGetOpen] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)

  async function createBranch(v) {
    if (!activeRepo) {
      setError('Pick a repository first (Repositories tab).')
      return
    }
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const res = await bitbucketApi.createRepoBranch(activeRepo, v.branch_name, v.from_commit)
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
      } else {
        setNotice(`✅ Branch "${res.name}" created.`)
        setCreateOpen(false)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function getBranch(v) {
    if (!activeRepo) {
      setError('Pick a repository first (Repositories tab).')
      return
    }
    setBusy(true)
    setError('')
    setBranchInfo(null)
    try {
      const res = await bitbucketApi.getBranch(activeRepo, v.branch_name)
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
      } else {
        setBranchInfo(res)
        setGetOpen(false)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!activeRepo) {
    return (
      <Panel title="Branches" hint="no repo selected">
        <p className="empty">Select a repository first (Repositories tab → Use in tabs).</p>
      </Panel>
    )
  }

  return (
    <>
      <Panel title="Branches" hint={activeRepo} wide>
        <div className="panel-toolbar">
          <button className="btn btn-primary btn-sm" onClick={() => setCreateOpen(true)}>
            + Create Branch
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => setGetOpen(true)}>
            Get Branch Info
          </button>
        </div>

        {error && <p className="bb-notice">⚠️ {error}</p>}
        {notice && <p className="bb-notice">{notice}</p>}

        {branchInfo && (
          <div className="kv-grid">
            <K k="Name" v={branchInfo.name} />
            <K k="Target hash" v={branchInfo.target?.hash} />
            <K k="Type" v={branchInfo.type} />
            <K
              k="Latest commit"
              v={branchInfo.target?.message ? String(branchInfo.target.message).split('\n')[0] : ''}
            />
            <K k="Author" v={branchInfo.target?.author?.raw} />
            <K k="Date" v={branchInfo.target?.date} />
          </div>
        )}
      </Panel>

      <FormModal
        open={createOpen}
        title="Create Branch"
        submitText="Create"
        busy={busy}
        error={error}
        fields={[
          { name: 'branch_name', label: 'Branch name', required: true },
          { name: 'from_commit', label: 'From commit SHA (optional)', default: '' },
        ]}
        onSubmit={createBranch}
        onClose={() => setCreateOpen(false)}
      />

      <FormModal
        open={getOpen}
        title="Get Branch Info"
        submitText="Fetch"
        busy={busy}
        error={error}
        fields={[{ name: 'branch_name', label: 'Branch name', required: true }]}
        onSubmit={getBranch}
        onClose={() => setGetOpen(false)}
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
