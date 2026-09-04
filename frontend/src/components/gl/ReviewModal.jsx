import { useEffect } from 'react'
import { ratingMeta, riskMeta } from './ui.jsx'

/**
 * Shows the verdict from the dedicated AI code-review agent.
 *
 * Props:
 *   open     : bool
 *   title    : string      – what was reviewed (e.g. "MR !42 — Fix login")
 *   loading  : bool
 *   error    : string
 *   verdict  : object|null  – { rating, risk_factor, risk_score, summary,
 *                               findings[], good_points[], recommendation, ... }
 *   onClose  : () => void
 */
export default function ReviewModal({ open, title, loading, error, verdict, onClose }) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const r = verdict ? ratingMeta(verdict.rating) : null
  const risk = verdict ? riskMeta(verdict.risk_factor) : null

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal gl-review-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>🔍 AI Code Review</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="modal-body">
          <p className="gl-review-target">{title}</p>

          {loading && (
            <div className="spinner">Reviewing previous vs current code…</div>
          )}
          {error && <p className="ff-error">⚠️ {error}</p>}

          {verdict && !loading && (
            <>
              <div className="gl-verdict-row">
                <span className={`gl-verdict-badge ${r.cls}`}>
                  {r.icon} {r.label}
                </span>
                <span className={`gl-risk-badge ${risk.cls}`}>{risk.label}</span>
                <span className="gl-risk-score">
                  risk score <strong>{verdict.risk_score}</strong>/100
                </span>
                <span className="gl-reco">→ {String(verdict.recommendation || '').replace('_', ' ')}</span>
              </div>

              <div className="gl-risk-meter">
                <div
                  className={`gl-risk-meter-fill ${risk.cls}`}
                  style={{ width: `${Math.max(3, Math.min(100, verdict.risk_score))}%` }}
                />
              </div>

              <p className="gl-review-summary">{verdict.summary}</p>

              <h3 className="sub-h">Findings ({verdict.findings?.length || 0})</h3>
              {(!verdict.findings || verdict.findings.length === 0) && (
                <p className="empty">No blocking findings reported. 🎉</p>
              )}
              <div className="mini-list">
                {(verdict.findings || []).map((f, i) => (
                  <div className="mini-item gl-finding" key={i}>
                    <span className={`gl-sev gl-sev-${f.severity}`}>{f.severity}</span>
                    <div className="gl-finding-body">
                      <span className="gl-finding-title">{f.title}</span>
                      {f.file && <span className="gl-finding-file mono">{f.file}</span>}
                      {f.detail && <span className="gl-finding-detail">{f.detail}</span>}
                    </div>
                  </div>
                ))}
              </div>

              {verdict.good_points?.length > 0 && (
                <>
                  <h3 className="sub-h">Good points</h3>
                  <ul className="gl-good-list">
                    {verdict.good_points.map((g, i) => (
                      <li key={i}>✔ {g}</li>
                    ))}
                  </ul>
                </>
              )}

              {verdict.parsed_ok === false && (
                <p className="confirm-detail">
                  Note: the model did not return clean JSON — this verdict was inferred
                  from its raw response.
                </p>
              )}
            </>
          )}
        </div>

        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
