const BASE = '/bitbucket'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json()
}

export const bitbucketApi = {
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
}
