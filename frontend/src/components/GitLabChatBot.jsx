import { useEffect, useRef, useState } from 'react'
import { gitlabApi } from '../gitlabApi.js'
import ConfirmModal from './ConfirmModal.jsx'

// Keywords that indicate a human-gated GitLab action the user is requesting.
const GATED_KEYWORDS = [
  { label: 'approve', re: /\bapprove\s+(this\s+|the\s+)?(mr|!?\d+|merge request)/i },
  { label: 'merge', re: /\bmerg(e|ing)\b(?!\s+requests?\b)/i },
  { label: 'close', re: /\b(close|closing|decline)\s+(the\s+)?(mr|!?\d+|merge request)\b/i },
  { label: 'delete', re: /\b(delete|remove)\s+(the\s+)?(branch|project|repo|repository)\b/i },
]
// NOTE: create / comment / branch-create are still human-gated — the backend
// tools refuse without confirmed=True and the agent asks for confirmation
// in-chat. We deliberately do NOT keyword-gate them here, so ordinary read
// requests ("list open MRs", "show new commits") are never blocked.

function detectGatedAction(text) {
  for (const kw of GATED_KEYWORDS) if (kw.re.test(text)) return kw.label
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

const META = {
  approve: { title: 'Approve Merge Request', message: 'You asked to approve an MR. Confirm to send this to the GitLab agent?', confirmText: 'Approve', danger: false },
  merge: { title: 'Merge Merge Request', message: 'You asked to merge an MR. Confirm to send this to the GitLab agent?', confirmText: 'Merge', danger: true },
  close: { title: 'Close Merge Request', message: 'You asked to close an MR. Confirm to send this to the GitLab agent?', confirmText: 'Close', danger: true },
  delete: { title: 'Delete', message: 'You asked to delete a branch or project. This is irreversible. Confirm to send this to the GitLab agent?', confirmText: 'Delete', danger: true },
}

export default function GitLabChatBot({ open, onToggle }) {
  const [messages, setMessages] = useState([
    {
      role: 'agent',
      text: 'Hi! I manage your GitLab workspace — projects, merge requests, branches, commits and pipelines. Try: "List open merge requests" or "Review MR !12 in group/app".',
    },
  ])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [pendingAction, setPendingAction] = useState(null)
  const [confirmingMessage, setConfirmingMessage] = useState('')
  const listRef = useRef(null)

  useEffect(() => {
    listRef.current?.scrollTo(0, listRef.current.scrollHeight)
  }, [messages, busy])

  async function send(confirmedMessage) {
    const msg = (confirmedMessage ?? input).trim()
    if (!msg || busy) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text: msg }])
    setBusy(true)
    try {
      const { reply } = await gitlabApi.chat(msg)
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
      setPendingAction(gated)
      setConfirmingMessage(msg)
      return
    }
    send(msg)
  }

  async function reset() {
    try {
      await gitlabApi.resetChat()
    } catch {
      /* ignore */
    }
    setMessages([{ role: 'agent', text: 'Conversation cleared. What can I do for you?' }])
  }

  return (
    <>
      <button className="chat-fab gl-fab" onClick={onToggle} aria-label="Toggle GitLab chatbot">
        {open ? '✕' : '🦊'}
      </button>

      {open && (
        <div className="chat-panel">
          <div className="chat-head">
            <span className="chat-title">GitLab Assistant</span>
            <button className="icon-btn small" onClick={reset} title="Reset conversation">⟲</button>
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
              placeholder="Ask about MRs, commits, projects…"
              disabled={busy}
              autoFocus
            />
            <button onClick={onSubmit} disabled={busy || !input.trim()}>Send</button>
          </div>
        </div>
      )}

      {pendingAction && (
        <ConfirmModal
          open
          {...META[pendingAction]}
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
