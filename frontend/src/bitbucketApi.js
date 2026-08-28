const BASE = '/bitbucket'

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

export const bitbucketApi = {
  // ── Existing dashboard / chat ─────────────────────────────
  dashboard: () => request('/dashboard'),
  commits: () => request('/commits'),
  pendingPrs: () => request('/pending-prs'),
  chat: (message) =>
    request('/chat', { method: 'POST', body: JSON.stringify({ message }) }),

  approvePr: (repo_slug, pr_id, workspace = '') =>
    request('/pr/approve', {
      method: 'POST',
      body: JSON.stringify({ repo_slug, pr_id, workspace, confirmed: true }),
    }),
  declinePr: (repo_slug, pr_id, workspace = '') =>
    request('/pr/decline', {
      method: 'POST',
      body: JSON.stringify({ repo_slug, pr_id, workspace, confirmed: true }),
    }),
  mergePr: (repo_slug, pr_id, workspace = '') =>
    request('/pr/merge', {
      method: 'POST',
      body: JSON.stringify({ repo_slug, pr_id, workspace, confirmed: true }),
    }),
  createRepo: (repo_name, is_private = true, description = '', workspace = '') =>
    request('/repo/create', {
      method: 'POST',
      body: JSON.stringify({ repo_name, is_private, description, workspace }),
    }),
  deleteRepo: (repo_slug, workspace = '') =>
    request('/repo/delete', {
      method: 'POST',
      body: JSON.stringify({ repo_slug, workspace, confirmed: true }),
    }),
  createBranch: (repo_slug, branch_name, from_commit = '', workspace = '') =>
    request('/branch/create', {
      method: 'POST',
      body: JSON.stringify({ repo_slug, branch_name, from_commit, workspace }),
    }),
  setBranchPermission: (repo_slug, branch_pattern, kind, value = '', workspace = '') =>
    request('/branch/permission', {
      method: 'POST',
      body: JSON.stringify({ repo_slug, branch_pattern, kind, value, workspace, confirmed: true }),
    }),
  inviteCollaborator: (repo_slug, email_or_uuid, role = 'write', workspace = '') =>
    request('/collaborator/invite', {
      method: 'POST',
      body: JSON.stringify({ repo_slug, email_or_uuid, role, workspace }),
    }),

  // ── Workspaces ────────────────────────────────────────────
  listWorkspaces: () => request('/workspaces'),
  getWorkspace: (workspace = '') => request(`/workspace${qs({ workspace })}`),

  // ── Repositories / files / branches / commits ─────────────
  listRepos: (workspace = '') => request(`/repos${qs({ workspace })}`),
  getRepo: (repo_slug, workspace = '') => request(`/repo${qs({ repo_slug, workspace })}`),
  getDefaultReviewers: (repo_slug, workspace = '') =>
    request(`/repo/default-reviewers${qs({ repo_slug, workspace })}`),
  getFile: (repo_slug, path, revision = '', workspace = '') =>
    request(`/repo/file${qs({ repo_slug, path, revision, workspace })}`),
  getCommit: (repo_slug, revision = '', workspace = '') =>
    request(`/repo/commit${qs({ repo_slug, revision, workspace })}`),
  createCommit: (repo_slug, file_path, content, message, branch = '', workspace = '') =>
    request('/repo/commit', {
      method: 'POST',
      body: JSON.stringify({ repo_slug, file_path, content, message, branch, workspace }),
    }),
  getBranch: (repo_slug, branch_name, workspace = '') =>
    request(`/repo/branch${qs({ repo_slug, branch_name, workspace })}`),
  createRepoBranch: (repo_slug, branch_name, from_commit = '', workspace = '') =>
    request('/repo/branch', {
      method: 'POST',
      body: JSON.stringify({ repo_slug, branch_name, from_commit, workspace }),
    }),

  // ── Pull requests ─────────────────────────────────────────
  listPrs: (repo_slug, state = 'OPEN', workspace = '', pagelen = 50) =>
    request(`/pr/list${qs({ repo_slug, state, workspace, pagelen })}`),
  getPr: (repo_slug, pr_id, workspace = '') =>
    request(`/pr${qs({ repo_slug, pr_id, workspace })}`),
  getPrDiff: (repo_slug, pr_id, workspace = '') =>
    request(`/pr/diff${qs({ repo_slug, pr_id, workspace })}`),
  createPr: (repo_slug, title, source_branch = '', destination_branch = '', description = '', workspace = '') =>
    request('/pr/create', {
      method: 'POST',
      body: JSON.stringify({ repo_slug, title, source_branch, destination_branch, description, workspace }),
    }),
  listPrComments: (repo_slug, pr_id, workspace = '') =>
    request(`/pr/comments${qs({ repo_slug, pr_id, workspace })}`),
  addPrComment: (repo_slug, pr_id, content, workspace = '') =>
    request('/pr/comment', {
      method: 'POST',
      body: JSON.stringify({ repo_slug, pr_id, content, workspace }),
    }),
  updatePrComment: (repo_slug, pr_id, comment_id, content, workspace = '') =>
    request('/pr/comment', {
      method: 'PUT',
      body: JSON.stringify({ repo_slug, pr_id, comment_id, content, workspace }),
    }),
  listPrTasks: (repo_slug, pr_id, workspace = '') =>
    request(`/pr/tasks${qs({ repo_slug, pr_id, workspace })}`),
  createPrTask: (repo_slug, pr_id, content, workspace = '') =>
    request('/pr/task', {
      method: 'POST',
      body: JSON.stringify({ repo_slug, pr_id, content, workspace }),
    }),
  updatePrTask: (repo_slug, pr_id, task_id, content = '', state = '', workspace = '') =>
    request('/pr/task', {
      method: 'PUT',
      body: JSON.stringify({ repo_slug, pr_id, task_id, content, state, workspace }),
    }),
  userPullRequests: (selected_user, workspace = '', state = 'OPEN') =>
    request(`/pr/user${qs({ selected_user, workspace, state })}`),

  // ── Pipelines ─────────────────────────────────────────────
  listPipelines: (repo_slug, workspace = '', pagelen = 25) =>
    request(`/pipelines${qs({ repo_slug, workspace, pagelen })}`),
  getPipeline: (repo_slug, pipeline_uuid, workspace = '') =>
    request(`/pipeline${qs({ repo_slug, pipeline_uuid, workspace })}`),
  runPipeline: (repo_slug, ref_type = 'branch', ref_name = '', selector_type = 'custom', selector_pattern = '**', variables = null, workspace = '') =>
    request('/pipeline/run', {
      method: 'POST',
      body: JSON.stringify({ repo_slug, ref_type, ref_name, selector_type, selector_pattern, variables, workspace }),
    }),
  getPipelineSteps: (repo_slug, pipeline_uuid, workspace = '', pagelen = 25) =>
    request(`/pipeline/steps${qs({ repo_slug, pipeline_uuid, workspace, pagelen })}`),
  getPipelineStep: (repo_slug, pipeline_uuid, step_uuid, workspace = '') =>
    request(`/pipeline/step${qs({ repo_slug, pipeline_uuid, step_uuid, workspace })}`),
  getPipelineStepLog: (repo_slug, pipeline_uuid, step_uuid, workspace = '') =>
    request(`/pipeline/step/log${qs({ repo_slug, pipeline_uuid, step_uuid, workspace })}`),
  analyzePrFailures: (repo_slug, pr_id, workspace = '') =>
    request(`/pipeline/analyze/pr-failures${qs({ repo_slug, pr_id, workspace })}`),
  analyzeStepFailure: (repo_slug, pipeline_uuid, step_uuid, workspace = '', log_lines = 200) =>
    request(`/pipeline/analyze/step-failure${qs({ repo_slug, pipeline_uuid, step_uuid, workspace, log_lines })}`),

  // ── Deployments & Environments ────────────────────────────
  listDeployments: (repo_slug, workspace = '', pagelen = 25) =>
    request(`/deployments${qs({ repo_slug, workspace, pagelen })}`),
  getDeployment: (repo_slug, deployment_uuid, workspace = '') =>
    request(`/deployment${qs({ repo_slug, deployment_uuid, workspace })}`),
  listEnvironments: (repo_slug, workspace = '', pagelen = 25) =>
    request(`/environments${qs({ repo_slug, workspace, pagelen })}`),
  getEnvironment: (repo_slug, environment_uuid, workspace = '') =>
    request(`/environment${qs({ repo_slug, environment_uuid, workspace })}`),
  createEnvironment: (repo_slug, name, environment_type = 'Production', workspace = '') =>
    request('/environment', {
      method: 'POST',
      body: JSON.stringify({ repo_slug, name, environment_type, workspace }),
    }),
  deleteEnvironment: (repo_slug, environment_uuid, workspace = '') =>
    request('/environment/delete', {
      method: 'POST',
      body: JSON.stringify({ repo_slug, environment_uuid, workspace, confirmed: true }),
    }),
  updateEnvironment: (repo_slug, environment_uuid, update = null, workspace = '') =>
    request('/environment/update', {
      method: 'POST',
      body: JSON.stringify({ repo_slug, environment_uuid, update, workspace }),
    }),
}
