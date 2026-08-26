import { useEffect, useState } from 'react'

function fmt(msRemaining) {
  const neg = msRemaining < 0
  let s = Math.floor(Math.abs(msRemaining) / 1000)
  const d = Math.floor(s / 86400)
  s -= d * 86400
  const h = Math.floor(s / 3600)
  s -= h * 3600
  const m = Math.floor(s / 60)
  s -= m * 60

  let text
  if (d > 0) text = `${d}d ${h}h`
  else if (h > 0) text = `${h}h ${m}m`
  else if (m > 0) text = `${m}m ${s}s`
  else text = `${s}s`

  return { text, neg }
}

/**
 * Live countdown to a due date.
 * epochSec — Unix timestamp in SECONDS
 */
export default function Countdown({ epochSec }) {
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  if (!epochSec) return <span className="cd cd-none">no due date</span>

  const target = epochSec * 1000
  const { text, neg } = fmt(target - now)

  let cls = 'cd'
  const diffHrs = (target - now) / 3600000
  if (neg) cls += ' cd-over'
  else if (diffHrs <= 1) cls += ' cd-crit'
  else if (diffHrs <= 24) cls += ' cd-warn'

  return (
    <span className={cls}>
      {neg ? `overdue by ${text}` : `due in ${text}`}
    </span>
  )
}
