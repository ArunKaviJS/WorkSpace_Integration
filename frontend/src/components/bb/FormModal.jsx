import { useEffect, useState } from 'react'

/**
 * Generic labelled-form modal used by Bitbucket panels to collect inputs for a
 * mutating action (create PR, run pipeline, create repo, etc.).
 *
 * Props:
 *   open      : bool
 *   title     : string
 *   fields    : array of { name, label, type?, required?, default?, options?, placeholder? }
 *   submitText: string
 *   danger    : bool
 *   busy      : bool
 *   error     : string
 *   onSubmit  : (values: object) => void
 *   onClose   : () => void
 */
export default function FormModal({
  open,
  title,
  fields = [],
  submitText = 'Submit',
  danger = false,
  busy = false,
  error = '',
  onSubmit,
  onClose,
}) {
  const [values, setValues] = useState({})

  useEffect(() => {
    if (open) {
      const init = {}
      fields.forEach((f) => {
        init[f.name] = f.default !== undefined ? f.default : ''
      })
      setValues(init)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => e.key === 'Escape' && !busy && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, busy, onClose])

  if (!open) return null

  function set(name, value) {
    setValues((v) => ({ ...v, [name]: value }))
  }

  return (
    <div className="modal-backdrop" onClick={() => !busy && onClose()}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} disabled={busy} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="modal-body ff-form">
          {fields.map((f) => (
            <div className="ff-field" key={f.name}>
              <label>
                {f.label}
                {f.required ? <span className="ff-req"> *</span> : null}
              </label>
              {f.type === 'textarea' ? (
                <textarea
                  rows={f.rows || 4}
                  value={values[f.name] ?? ''}
                  onChange={(e) => set(f.name, e.target.value)}
                  placeholder={f.placeholder || ''}
                />
              ) : f.type === 'select' ? (
                <select value={values[f.name] ?? ''} onChange={(e) => set(f.name, e.target.value)}>
                  {(f.options || []).map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type={f.type === 'number' ? 'number' : 'text'}
                  value={values[f.name] ?? ''}
                  onChange={(e) => set(f.name, e.target.value)}
                  placeholder={f.placeholder || ''}
                />
              )}
            </div>
          ))}

          {error && <p className="ff-error">⚠️ {error}</p>}

          <div className="modal-actions">
            <button className="btn btn-ghost" onClick={onClose} disabled={busy}>
              Cancel
            </button>
            <button
              className={`btn ${danger ? 'btn-danger' : 'btn-primary'}`}
              onClick={() => onSubmit(values)}
              disabled={busy}
            >
              {busy ? 'Working…' : submitText}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
