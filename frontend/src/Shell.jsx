import { useEffect, useState } from 'react'
import App from './App.jsx'
import BitbucketDashboard from './pages/BitbucketDashboard.jsx'
import GitLabDashboard from './pages/GitLabDashboard.jsx'

function parseHash() {
  return (window.location.hash || '#/clickup').replace(/^#/, '')
}

export default function Shell() {
  const [route, setRoute] = useState(parseHash)

  useEffect(() => {
    const onHash = () => setRoute(parseHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const isBitbucket = route.startsWith('/bitbucket')
  const isGitlab = route.startsWith('/gitlab')
  const isClickup = !isBitbucket && !isGitlab

  let page = <App />
  if (isBitbucket) page = <BitbucketDashboard />
  else if (isGitlab) page = <GitLabDashboard />

  return (
    <div className="shell">
      <aside className="shell-sidebar">
        <div className="shell-brand">AI Command Center</div>
        <nav className="shell-nav">
          <a href="#/clickup" className={`shell-link ${isClickup ? 'active' : ''}`}>
            ClickUp
          </a>
          <a href="#/bitbucket/dashboard" className={`shell-link ${isBitbucket ? 'active' : ''}`}>
            Bitbucket
          </a>
          <a href="#/gitlab/dashboard" className={`shell-link ${isGitlab ? 'active' : ''}`}>
            GitLab
          </a>
        </nav>
      </aside>

      <main className="shell-content">{page}</main>
    </div>
  )
}
