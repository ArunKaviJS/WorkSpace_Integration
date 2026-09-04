const BASE = '/gitlab'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json()
}

function qs(params) {
  const p = new URLSearchParams()
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') p.set(k, String(v))
  })
  const s = p.toString()
  return s ? `?${s}` : ''
}

export const gitlabApi = {
  // ── Chat / identity ──────────────────────────────────────
  chat: (message) =>
    request('/chat', { method: 'POST', body: JSON.stringify({ message }) }),
  resetChat: () => request('/chat/reset', { method: 'POST' }),
  me: () => request('/me'),

  // ── Dashboard ────────────────────────────────────────────
  dashboard: () => request('/dashboard'),
  commits: () => request('/commits'),
  pendingMrs: () => request('/pending-mrs'),

  // ── Projects / commits / files ───────────────────────────
  listProjects: (search = '', limit = 50) => request(`/projects${qs({ search, limit })}`),
  getProject: (project_id) => request(`/project${qs({ project_id })}`),
  createProject: (payload) =>
    request('/project/create', {
      method: 'POST',
      body: JSON.stringify({ confirmed: true, ...payload }),
    }),
  deleteProject: (project_id) =>
    request('/project/delete', {
      method: 'POST',
      body: JSON.stringify({ project_id, confirmed: true }),
    }),
  projectCommits: (project_id, ref = '', limit = 20) =>
    request(`/project/commits${qs({ project_id, ref, limit })}`),
  getFile: (project_id, path, ref = '') =>
    request(`/project/file${qs({ project_id, path, ref })}`),
  compare: (project_id, from_sha, to_sha) =>
    request(`/compare${qs({ project_id, from_sha, to_sha })}`),
  getCommit: (project_id, sha) => request(`/commit${qs({ project_id, sha })}`),
  getCommitDiff: (project_id, sha) => request(`/commit/diff${qs({ project_id, sha })}`),

  // ── Branches ─────────────────────────────────────────────
  listBranches: (project_id, search = '', limit = 100) =>
    request(`/branches${qs({ project_id, search, limit })}`),
  getBranch: (project_id, branch) => request(`/branch${qs({ project_id, branch })}`),
  createBranch: (project_id, branch, ref = '') =>
    request('/branch/create', {
      method: 'POST',
      body: JSON.stringify({ project_id, branch, ref, confirmed: true }),
    }),
  deleteBranch: (project_id, branch) =>
    request('/branch/delete', {
      method: 'POST',
      body: JSON.stringify({ project_id, branch, confirmed: true }),
    }),

  // ── Merge requests ───────────────────────────────────────
  listMrs: (project_id, state = 'opened', limit = 50) =>
    request(`/mrs${qs({ project_id, state, limit })}`),
  getMr: (project_id, mr_iid) => request(`/mr${qs({ project_id, mr_iid })}`),
  getMrChanges: (project_id, mr_iid) => request(`/mr/changes${qs({ project_id, mr_iid })}`),
  listMrNotes: (project_id, mr_iid) => request(`/mr/notes${qs({ project_id, mr_iid })}`),
  addMrNote: (project_id, mr_iid, body) =>
    request('/mr/note', {
      method: 'POST',
      body: JSON.stringify({ project_id, mr_iid, body, confirmed: true }),
    }),
  createMr: (project_id, source_branch, target_branch, title, description = '') =>
    request('/mr/create', {
      method: 'POST',
      body: JSON.stringify({
        project_id, source_branch, target_branch, title, description, confirmed: true,
      }),
    }),
  approveMr: (project_id, mr_iid) =>
    request('/mr/approve', {
      method: 'POST',
      body: JSON.stringify({ project_id, mr_iid, confirmed: true }),
    }),
  unapproveMr: (project_id, mr_iid) =>
    request('/mr/unapprove', {
      method: 'POST',
      body: JSON.stringify({ project_id, mr_iid, confirmed: true }),
    }),
  mergeMr: (project_id, mr_iid, opts = {}) =>
    request('/mr/merge', {
      method: 'POST',
      body: JSON.stringify({ project_id, mr_iid, confirmed: true, ...opts }),
    }),
  closeMr: (project_id, mr_iid) =>
    request('/mr/close', {
      method: 'POST',
      body: JSON.stringify({ project_id, mr_iid, confirmed: true }),
    }),

  // ── AI code review (dedicated agent) ─────────────────────
  reviewMr: (project_id, mr_iid) => request(`/mr/review${qs({ project_id, mr_iid })}`),
  reviewCommit: (project_id, sha) => request(`/commit/review${qs({ project_id, sha })}`),
  reviewCompare: (project_id, from_sha, to_sha) =>
    request(`/review/compare${qs({ project_id, from_sha, to_sha })}`),

  // ── Pipelines ────────────────────────────────────────────
  listPipelines: (project_id, ref = '', limit = 20) =>
    request(`/pipelines${qs({ project_id, ref, limit })}`),
  getPipeline: (project_id, pipeline_id) =>
    request(`/pipeline${qs({ project_id, pipeline_id })}`),
  pipelineJobs: (project_id, pipeline_id) =>
    request(`/pipeline/jobs${qs({ project_id, pipeline_id })}`),
}
