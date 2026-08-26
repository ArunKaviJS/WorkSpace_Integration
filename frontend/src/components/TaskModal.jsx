import { useEffect } from 'react'
import Countdown from './Countdown.jsx'

export default function TaskModal({ task, onClose }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!task) return null

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>{task.name}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="modal-body">
          <div className="detail-row">
            <span className="label">Status</span>
            <span className={`status-chip ${task.is_complete ? 's-done' : 's-open'}`}>
              {task.status || 'unknown'}
            </span>
          </div>
          <div className="detail-row">
            <span className="label">Due</span>
            <Countdown epochSec={task.due_date_epoch} />
          </div>
          <div className="detail-row">
            <span className="label">Assignees</span>
            <span>{task.assignees?.length ? task.assignees.join(', ') : 'Unassigned'}</span>
          </div>
          {task.priority && (
            <div className="detail-row">
              <span className="label">Priority</span>
              <span>{task.priority}</span>
            </div>
          )}
          {task.tags?.length > 0 && (
            <div className="detail-row">
              <span className="label">Tags</span>
              <span className="tags">
                {task.tags.map((t) => (
                  <span key={t} className="tag">{t}</span>
                ))}
              </span>
            </div>
          )}
          <div className="detail-row">
            <span className="label">Task ID</span>
            <code>{task.id}</code>
          </div>
          {task.description && (
            <div className="desc-block">
              <span className="label">Description</span>
              <p
                className="desc"
                dangerouslySetInnerHTML={{ __html: task.description }}
              />
            </div>
          )}
        </div>

        {task.url && (
          <a
            className="open-clickup"
            href={task.url}
            target="_blank"
            rel="noreferrer"
          >
            Open in ClickUp ↗
          </a>
        )}
      </div>
    </div>
  )
}
