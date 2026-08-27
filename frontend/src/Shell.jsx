import { useEffect, useState } from 'react'
import App from './App.jsx'
import BitbucketDashboard from './pages/BitbucketDashboard.jsx'

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

  return (
    <div className="shell">
      <aside className="shell-sidebar">
        <div className="shell-brand">AI Command Center</div>
        <nav className="shell-nav">
          <a
            href="#/clickup"
            className={`shell-link ${!isBitbucket ? 'active' : ''}`}
          >
            ClickUp
          </a>
          <a
            href="#/bitbucket/dashboard"
            className={`shell-link ${isBitbucket ? 'active' : ''}`}
          >
            Bitbucket
          </a>
        </nav>
      </aside>

      <main className="shell-content">
        {isBitbucket ? <BitbucketDashboard /> : <App />}
      </main>
    </div>
  )
}
