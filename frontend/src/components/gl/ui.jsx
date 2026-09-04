import { createContext, useContext } from 'react'

// Reuse the Bitbucket panel primitives so both tabs share one visual language.
export { Panel, Empty, StatusChip } from '../bb/ui.jsx'

// Shares the currently selected GitLab project (id or 'namespace/path') across
// all GitLab tabs so the user only picks a project once per session.
export const ProjectContext = createContext({
  project: '',
  projectLabel: '',
  setProject: () => {},
})

export function useProject() {
  return useContext(ProjectContext)
}

// ── AI-review verdict helpers ──────────────────────────────
export const RATING_META = {
  good: { label: 'GOOD', cls: 'gl-verdict-good', icon: '✅' },
  need_to_check: { label: 'NEED TO CHECK', cls: 'gl-verdict-check', icon: '🟠' },
  bad: { label: 'BAD', cls: 'gl-verdict-bad', icon: '⛔' },
}

export const RISK_META = {
  low: { label: 'Low risk', cls: 'gl-risk-low' },
  medium: { label: 'Medium risk', cls: 'gl-risk-medium' },
  high: { label: 'High risk', cls: 'gl-risk-high' },
}

export function ratingMeta(rating) {
  return RATING_META[rating] || RATING_META.need_to_check
}

export function riskMeta(risk) {
  return RISK_META[risk] || RISK_META.medium
}
