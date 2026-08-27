import { useEffect } from 'react'

/**
 * Human-gated confirmation modal, mirroring the existing modal style.
 * Rendered before any destructive / irreversible Bitbucket action fires.
 *
 * Props:
 *   open      : bool        – whether to show the modal
 *   title     : string      – modal heading
 *   message   : string      – explanation of what will happen
 *   detail    : string      – optional small caption (e.g. repo/PR)
 *   confirmText: string     – label for the confirm button (default "Confirm")
 *   danger    : bool        – red confirm style
 *   busy      : bool        – disables buttons while a request is pending
 *   onConfirm : () => void  – fired only when the user clicks Confirm
 *   onClose   : () => void  – fired on Cancel / backdrop / Escape
 */
export default function ConfirmModal({
  open,
  title = 'Are you sure?',
  message = 'This action cannot be undone.',
  detail = '',
  confirmText = 'Confirm',
  danger = false,
  busy = false,
  onConfirm,
  onClose,
}) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => e.key === 'Escape' && !busy && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, busy, onClose])

  if (!open) return null

  return (
    <div className="modal-backdrop" onClick={() => !busy && onClose()}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} disabled={busy} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="modal-body">
          <p className="confirm-msg">{message}</p>
          {detail && <p className="confirm-detail">{detail}</p>}
        </div>

        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button
            className={`btn ${danger ? 'btn-danger' : 'btn-primary'}`}
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? 'Working…' : confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
