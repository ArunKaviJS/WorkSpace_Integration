import { useCallback, useEffect, useState } from 'react'
import { bitbucketApi } from '../../bitbucketApi.js'
import { Panel, Empty, StatusChip, useRepo } from './ui.jsx'
import FormModal from './FormModal.jsx'

export default function PipelinesPanel() {
  const { repo: activeRepo } = useRepo()
  const [pipelines, setPipelines] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)

  const [runOpen, setRunOpen] = useState(false)
  const [steps, setSteps] = useState(null)
  const [log, setLog] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const [prAnalysis, setPrAnalysis] = useState(null)

  const load = useCallback(async () => {
    if (!activeRepo) return
    setLoading(true)
    setError('')
    try {
      const res = await bitbucketApi.listPipelines(activeRepo)
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
        setPipelines([])
      } else {
        setPipelines(res.values || [])
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [activeRepo])

  useEffect(() => {
    setPipelines([])
    setSteps(null)
    setLog(null)
    setAnalysis(null)
    if (activeRepo) load()
  }, [activeRepo, load])

  async function runPipeline(v) {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const res = await bitbucketApi.runPipeline(
        activeRepo,
        v.ref_type,
        v.ref_name,
        v.selector_type,
        v.selector_pattern
      )
      if (res && res.error) {
        setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error))
      } else {
        setNotice(`▶️ Pipeline scheduled (${res.uuid}).`)
        setRunOpen(false)
        load()
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function showSteps(pl) {
    setError('')
    setAnalysis(null)
    setLog(null)
    try {
      const res = await bitbucketApi.getPipelineSteps(activeRepo, pl.uuid)
      setSteps({ pipeline: pl, values: res.values || (Array.isArray(res) ? res : []) })
    } catch (err) {
      setError(err.message)
    }
  }

  async function showLog(step) {
    if (!steps) return
    setError('')
    setLog(null)
    setAnalysis(null)
    try {
      const res = await bitbucketApi.getPipelineStepLog(activeRepo, steps.pipeline.uuid, step.uuid)
      setLog(typeof res?.log === 'string' ? res.log : JSON.stringify(res, null, 2))
    } catch (err) {
      setError(err.message)
    }
  }

  async function analyzeStep(step) {
    if (!steps) return
    setError('')
    setLog(null)
    setAnalysis(null)
    try {
      const res = await bitbucketApi.analyzeStepFailure(activeRepo, steps.pipeline.uuid, step.uuid)
      setAnalysis(res)
    } catch (err) {
      setError(err.message)
    }
  }

  if (!activeRepo) {
    return (
      <Panel title="Pipelines" hint="no repo selected">
        <p className="empty">Select a repository first (Repositories tab → Use in tabs).</p>
      </Panel>
    )
  }

  return (
    <>
      <Panel title="Pipelines" hint={activeRepo} wide>
        <div className="panel-toolbar">
          <button className="btn btn-primary btn-sm" onClick={() => setRunOpen(true)}>
            ▶ Run Pipeline
          </button>
          <button className="btn btn-ghost btn-sm" onClick={load} disabled={loading}>
            {loading ? 'Loading…' : '⟳ Refresh'}
          </button>
        </div>

        {error && <p className="bb-notice">⚠️ {error}</p>}
        {notice && <p className="bb-notice">{notice}</p>}
        {pipelines.length === 0 && !loading && <Empty text="No pipelines found." />}

        <div className="bb-table-wrap">
          <table className="bb-table">
            <thead>
              <tr>
                <th>Build</th>
                <th>State</th>
                <th>Branch</th>
                <th>Triggered</th>
                <th>Duration</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {pipelines.map((pl) => {
                const st = (pl.state?.name || '').toUpperCase()
                const stateVals = pl.state?.result?.name
                return (
                  <tr key={pl.uuid}>
                    <td className="mono">#{pl.build_number}</td>
                    <td><StatusChip state={stateVals || st} /></td>
                    <td className="mono">{pl.target?.ref_name || pl.target?.commit?.hash?.slice(0, 8)}</td>
                    <td>{pl.created_on ? new Date(pl.created_on).toLocaleString() : '—'}</td>
                    <td>{pl.build_seconds_used ? `${pl.build_seconds_used}s` : '—'}</td>
                    <td>
                      <div className="bb-actions">
                        <button className="btn btn-ghost btn-sm" onClick={() => showSteps(pl)}>
                          Steps
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Panel>

      {steps && (
        <Panel title={`Pipeline #${steps.pipeline.build_number} — Steps`} wide>
          <div className="bb-table-wrap">
            <table className="bb-table">
              <thead>
                <tr>
                  <th>Step</th>
                  <th>Name</th>
                  <th>State</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {steps.values.map((s) => (
                  <tr key={s.uuid}>
                    <td className="mono">{s.uuid?.slice(0, 8)}</td>
                    <td>{s.name || '—'}</td>
                    <td><StatusChip state={s.state?.result?.name || s.state?.name} /></td>
                    <td>
                      <div className="bb-actions">
                        <button className="btn btn-ghost btn-sm" onClick={() => showLog(s)}>
                          Log
                        </button>
                        <button className="btn btn-warn btn-sm" onClick={() => analyzeStep(s)}>
                          Analyze
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {log && (
        <Panel title="Step Log" wide>
          <pre className="code-block">{log}</pre>
        </Panel>
      )}

      {analysis && (
        <Panel title="Step Failure Analysis" wide>
          <div className="kv-grid">
            <K k="Step" v={analysis.step_name || analysis.step_uuid} />
            <K k="State" v={analysis.step_state} />
            <K k="Summary" v={analysis.summary} />
          </div>
          {(analysis.log_tail || []).length > 0 && (
            <pre className="code-block">{analysis.log_tail.join('\n')}</pre>
          )}
        </Panel>
      )}

      <FormModal
        open={runOpen}
        title="Run Pipeline"
        submitText="Run"
        busy={busy}
        error={error}
        fields={[
          { name: 'ref_type', label: 'Ref type', type: 'select', default: 'branch', options: ['branch', 'commit', 'pull_request'] },
          { name: 'ref_name', label: 'Ref name (branch/commit)' },
          { name: 'selector_type', label: 'Selector type', type: 'select', default: 'custom', options: ['custom', 'branches', 'tags', 'pull-requests'] },
          { name: 'selector_pattern', label: 'Selector pattern', default: '**' },
        ]}
        onSubmit={runPipeline}
        onClose={() => setRunOpen(false)}
      />

      {/* PR failure analysis (needs pr_id) */}
      {prAnalysis && (
        <Panel title="PR Commit Failure Analysis" wide>
          <K k="Summary" v={prAnalysis.summary} />
          {(prAnalysis.failed_checks || []).map((c, i) => (
            <div className="mini-item" key={i}>
              <span className="mini-who">{c.name} ({c.key})</span>
              <span className="mini-text">{c.description}</span>
            </div>
          ))}
        </Panel>
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
