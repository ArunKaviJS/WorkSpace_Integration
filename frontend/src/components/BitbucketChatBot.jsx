import { useEffect, useRef, useState } from 'react'
import { bitbucketApi } from '../bitbucketApi.js'
import ConfirmModal from './ConfirmModal.jsx'

// Keywords that indicate a human-gated Bitbucket action the user is requesting.
// These trigger a confirmation modal before the request is sent.
const GATED_KEYWORDS = [
  { label: 'approve', re: /\b(approve|approving|approval)\b/i },
  { label: 'decline', re: /\b(declin|reject)\b/i },
  { label: 'merge', re: /\bmerg\b/i },
  { label: 'delete', re: /\b(delet|remove)\s+(repo|repository)\b/i },
]

function detectGatedAction(text) {
  for (const kw of GATED_KEYWORDS) {
    if (kw.re.test(text)) return kw.label
  }
  return null
}

function parseLinks(text) {
  const parts = []
  const re = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g
  let last = 0
  let m
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push({ type: 'text', value: text.slice(last, m.index) })
    parts.push({ type: 'link', label: m[1], href: m[2] })
    last = re.lastIndex
  }
  if (last < text.length) parts.push({ type: 'text', value: text.slice(last) })
  return parts.length ? parts : [{ type: 'text', value: text }]
}

function ChatMessage({ text }) {
  const parts = parseLinks(text)
  return (
    <>
      {parts.map((p, i) =>
        p.type === 'link' ? (
          <a key={i} className="chat-link-btn" href={p.href} target="_blank" rel="noreferrer">
            🔗 {p.label}
          </a>
        ) : (
          <span key={i}>{p.value}</span>
        )
      )}
    </>
  )
}

export default function BitbucketChatBot({ open, onToggle }) {
  const [messages, setMessages] = useState([
    {
      role: 'agent',
      text: 'Hi! I can help manage your Bitbucket workspace — repos, pull requests, branches and commits. Try: "Show me the latest commits" or "List open pull requests waiting for review".',
    },
  ])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)

  // Confirmation modal for human-gated actions
  const [pendingAction, setPendingAction] = useState(null)
  const [confirmingMessage, setConfirmingMessage] = useState('')

  const listRef = useRef(null)

  useEffect(() => {
    listRef.current?.scrollTo(0, listRef.current.scrollHeight)
  }, [messages, busy])

  function requestAction(type, message) {
    setPendingAction(type)
    setConfirmingMessage(message)
  }

  async function send(confirmedMessage) {
    const msg = (confirmedMessage ?? input).trim()
    if (!msg || busy) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text: msg }])
    setBusy(true)
    try {
      const { reply } = await bitbucketApi.chat(msg)
      setMessages((m) => [...m, { role: 'agent', text: reply ?? 'No reply.' }])
    } catch (err) {
      setMessages((m) => [...m, { role: 'agent', text: `⚠️ ${err.message}` }])
    } finally {
      setBusy(false)
    }
  }

  function onSubmit() {
    const msg = input.trim()
    if (!msg || busy) return
    const gated = detectGatedAction(msg)
    if (gated) {
      requestAction(gated, msg)
      return
    }
    send(msg)
  }

  async function reset() {
    await bitbucketApi.chat('reset')
    setMessages([{ role: 'agent', text: 'Conversation cleared. What can I do for you?' }])
  }

  const meta = {
    approve: {
      title: 'Approve Pull Request',
      message: 'You asked to approve a pull request. Confirm to send this to the Bitbucket agent?',
      confirmText: 'Approve',
      danger: false,
    },
    decline: {
      title: 'Decline Pull Request',
      message: 'You asked to decline a pull request. Confirm to send this to the Bitbucket agent?',
      confirmText: 'Decline',
      danger: true,
    },
    merge: {
      title: 'Merge Pull Request',
      message: 'You asked to merge a pull request. Confirm to send this to the Bitbucket agent?',
      confirmText: 'Merge',
      danger: true,
    },
    delete: {
      title: 'Delete Repository',
      message: 'You asked to delete a repository. This is irreversible. Confirm to send this to the Bitbucket agent?',
      confirmText: 'Delete',
      danger: true,
    },
  }

  return (
    <>
      <button className="chat-fab" onClick={onToggle} aria-label="Toggle Bitbucket chatbot">
        {open ? '✕' : '🪣'}
      </button>

      {open && (
        <div className="chat-panel">
          <div className="chat-head">
            <span className="chat-title">Bitbucket Assistant</span>
            <button className="icon-btn small" onClick={reset} title="Reset conversation">
              ⟲
            </button>
          </div>

          <div className="chat-msgs" ref={listRef}>
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.role}`}>
                <ChatMessage text={m.text} />
              </div>
            ))}
            {busy && (
              <div className="msg agent typing">
                thinking<span>.</span><span>.</span><span>.</span>
              </div>
            )}
          </div>

          <div className="chat-input">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && onSubmit()}
              placeholder="Ask about commits, PRs, repos…"
              disabled={busy}
              autoFocus
            />
            <button onClick={onSubmit} disabled={busy || !input.trim()}>
              Send
            </button>
          </div>
        </div>
      )}

      {pendingAction && (
        <ConfirmModal
          {...meta[pendingAction]}
          busy={busy}
          onConfirm={() => {
            const msg = confirmingMessage
            setPendingAction(null)
            send(msg)
          }}
          onClose={() => setPendingAction(null)}
        />
      )}
    </>
  )
}
