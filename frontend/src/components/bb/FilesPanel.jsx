import { useState } from 'react'
import { bitbucketApi } from '../../bitbucketApi.js'
import { Panel, Empty, useRepo } from './ui.jsx'
import FormModal from './FormModal.jsx'

export default function FilesPanel() {
  const { repo: activeRepo } = useRepo()
  const [path, setPath] = useState('')
  const [revision, setRevision] = useState('')
  const [file, setFile] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')

  // commit create
  const [commitOpen, setCommitOpen] = useState(false)
  const [reviewers, setReviewers] = useState(null)

  async function fetchFile() {
    if (!activeRepo) {
      setError('Pick a repository first (Repositories tab → "Use in tabs").')
      return
    }
    if (!path) {
      setError('Enter a file path, e.g. README.md or src/main.py')
      return
    }
    setError('')
    setBusy(true)
    setFile(null)
    try {
      const res = await bitbucketApi.getFile(activeRepo, path, revision)
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
      } else {
        setFile(res)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function fetchReviewers() {
    if (!activeRepo) {
      setError('Pick a repository first (Repositories tab).')
      return
    }
    setError('')
    setNotice('')
    setReviewers(null)
    try {
      const res = await bitbucketApi.getDefaultReviewers(activeRepo)
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
      } else {
        setReviewers(res)
      }
    } catch (err) {
      setError(err.message)
    }
  }

  async function createCommit(v) {
    if (!activeRepo) {
      setError('Pick a repository first (Repositories tab).')
      return
    }
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const res = await bitbucketApi.createCommit(activeRepo, v.file_path, v.content, v.message, v.branch)
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
      } else {
        setNotice(`✅ Commit created: ${res.commit_hash}`)
        setCommitOpen(false)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <Panel title="File Viewer" hint={activeRepo ? `repo: ${activeRepo}` : 'no repo selected'} wide>
        {!activeRepo && <Empty text="Select a repository first (Repositories tab → Use in tabs)." />}
        <div className="panel-toolbar">
          <input
            className="strip-input"
            placeholder="Path (e.g. README.md)"
            value={path}
            onChange={(e) => setPath(e.target.value)}
          />
          <input
            className="strip-input"
            placeholder="Revision / branch (optional)"
            value={revision}
            onChange={(e) => setRevision(e.target.value)}
          />
          <button className="btn btn-primary btn-sm" onClick={fetchFile} disabled={busy || !activeRepo}>
            Fetch
          </button>
          <button className="btn btn-ghost btn-sm" onClick={fetchReviewers} disabled={!activeRepo}>
            Default Reviewers
          </button>
          <button className="btn btn-warn btn-sm" onClick={() => setCommitOpen(true)} disabled={!activeRepo}>
            + Create Commit
          </button>
        </div>

        {error && <p className="bb-notice">⚠️ {error}</p>}
        {notice && <p className="bb-notice">{notice}</p>}

        {reviewers && (
          <div className="kv-grid">
            {(reviewers.values || []).map((r) => (
              <div className="kv-item" key={r.display_name || r.uuid}>
                <span className="kv-key">{r.display_name || r.nickname || 'User'}</span>
                <span className="kv-val">{r.uuid || ''}</span>
              </div>
            ))}
            {(reviewers.values || []).length === 0 && <Empty text="No default reviewers configured." />}
          </div>
        )}

        {file && (
          <Panel title={`${file.path} @ ${file.revision || 'HEAD'}`} wide>
            <pre className="code-block">{file.content}</pre>
          </Panel>
        )}
      </Panel>

      <FormModal
        open={commitOpen}
        title="Create Commit (push file)"
        submitText="Create Commit"
        busy={busy}
        error={error}
        fields={[
          { name: 'file_path', label: 'File path', required: true },
          { name: 'content', label: 'File content', type: 'textarea', rows: 6, required: true },
          { name: 'message', label: 'Commit message', required: true },
          { name: 'branch', label: 'Branch (optional, default main)', default: '' },
        ]}
        onSubmit={createCommit}
        onClose={() => setCommitOpen(false)}
      />
    </>
  )
}
