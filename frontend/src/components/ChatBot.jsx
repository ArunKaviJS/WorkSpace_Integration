import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'

export default function ChatBot({ open, onToggle }) {
  const [messages, setMessages] = useState([
    {
      role: 'agent',
      text: 'Hi! I can create and assign tasks for you. Try: "Create a task called Fix login bug in list 123456 assigned to user 789, priority High".',
    },
  ])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const listRef = useRef(null)

  useEffect(() => {
    listRef.current?.scrollTo(0, listRef.current.scrollHeight)
  }, [messages, busy])

  async function send() {
    const msg = input.trim()
    if (!msg || busy) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text: msg }])
    setBusy(true)
    try {
      const { reply } = await api.chat(msg)
      setMessages((m) => [...m, { role: 'agent', text: reply }])
    } catch (err) {
      setMessages((m) => [...m, { role: 'agent', text: `⚠️ ${err.message}` }])
    } finally {
      setBusy(false)
    }
  }

  async function reset() {
    await api.resetChat()
    setMessages([{ role: 'agent', text: 'Conversation cleared. What can I do for you?' }])
  }

  return (
    <>
      <button className="chat-fab" onClick={onToggle} aria-label="Toggle chatbot">
        {open ? '✕' : '🤖'}
      </button>

      {open && (
        <div className="chat-panel">
          <div className="chat-head">
            <span className="chat-title">Task Assistant</span>
            <button className="icon-btn small" onClick={reset} title="Reset conversation">
              ⟲
            </button>
          </div>

          <div className="chat-msgs" ref={listRef}>
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.role}`}>
                {m.text}
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
              onKeyDown={(e) => e.key === 'Enter' && send()}
              placeholder="Assign a task… e.g. Create task 'Deploy fix' in list 901234567"
              disabled={busy}
              autoFocus
            />
            <button onClick={send} disabled={busy || !input.trim()}>
              Send
            </button>
          </div>
        </div>
      )}
    </>
  )
}
