import Countdown from './Countdown.jsx'

const PRIO_LABEL = { 1: 'Urgent', 2: 'High', 3: 'Normal', 4: 'Low' }

export default function TaskCard({ task, variant = '', onClick }) {
  return (
    <button className={`task-card ${variant}`} onClick={() => onClick?.(task)}>
      <div className="task-top">
        <span className="task-name">{task.name}</span>
        {task.priority && (
          <span className={`prio p${task.priority}`}>
            {PRIO_LABEL[task.priority] || task.priority}
          </span>
        )}
      </div>
      <div className="task-bottom">
        <Countdown epochSec={task.due_date_epoch} />
        <span className="assignees">
          {task.assignees?.length ? task.assignees.join(', ') : 'Unassigned'}
        </span>
      </div>
    </button>
  )
}
