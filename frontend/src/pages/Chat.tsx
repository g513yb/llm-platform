import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { useOutletContext } from 'react-router-dom'
import type { ChatMsg, ChatSession, Domain } from '../types'
import { getBundle, now } from '../data/mock'

const API_BASE = import.meta.env.VITE_API_BASE || ''

export default function Chat() {
  const { domain } = useOutletContext<{ domain: Domain }>()
  const b = getBundle(domain.id)
  const [sessions, setSessions] = useState<ChatSession[]>(() =>
    b.sessions.map((s) => ({ ...s, messages: [...s.messages] })),
  )
  const [activeId, setActiveId] = useState(sessions[0].id)
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  const [adapters, setAdapters] = useState<{ id: string; name: string; loss: number }[]>([])
  const [activeAdapter, setActiveAdapter] = useState<{ id: string | null; name: string }>({ id: null, name: '基座模型' })
  const logRef = useRef<HTMLDivElement>(null)

  const active = sessions.find((s) => s.id === activeId)!

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: 'smooth' })
  }, [active.messages.length, thinking])

  useEffect(() => {
    const load = () => fetch(`${API_BASE}/api/adapters`).then((r) => r.json()).then(setAdapters).catch(() => {})
    load()
    fetch(`${API_BASE}/api/adapters/active`).then((r) => r.json()).then(setActiveAdapter).catch(() => {})
    const t = setInterval(load, 8000)
    return () => clearInterval(t)
  }, [])

  const onAdapterChange = async (e: ChangeEvent<HTMLSelectElement>) => {
    const v = e.target.value
    try {
      const r = await fetch(`${API_BASE}/api/adapters/load`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ adapterId: v || null }),
      }).then((x) => x.json())
      if (r.error) return
      setActiveAdapter({ id: r.id, name: r.name })
    } catch { /* 忽略 */ }
  }

  const send = async () => {
    const text = input.trim()
    if (!text || thinking) return
    setInput('')
    setThinking(true)
    const userMsg: ChatMsg = { role: 'user', content: text, time: now() }
    const history = [...active.messages, userMsg]
    setSessions((ss) => ss.map((s) => (s.id === activeId ? { ...s, messages: history } : s)))

    const apiMessages = [
      { role: 'system', content: `你是${domain.name}领域智能助手，请基于专业知识准确、简洁地回答用户问题。` },
      ...history.map((m) => ({ role: m.role, content: m.content })),
    ]

    const appendToken = (token: string) => {
      setSessions((ss) =>
        ss.map((s) => {
          if (s.id !== activeId) return s
          const msgs = [...s.messages]
          const last = msgs[msgs.length - 1]
          if (last && last.role === 'assistant') {
            msgs[msgs.length - 1] = { ...last, content: last.content + token }
          } else {
            msgs.push({ role: 'assistant', content: token, time: now() })
          }
          return { ...s, messages: msgs }
        }),
      )
    }

    try {
      const resp = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: apiMessages }),
      })
      if (!resp.ok || !resp.body) throw new Error('服务异常')
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6)
          if (data === '[DONE]') continue
          try {
            const obj = JSON.parse(data)
            if (obj.token) appendToken(obj.token)
          } catch {
            /* 忽略偶发解析错误 */
          }
        }
      }
    } catch {
      appendToken(`⚠️ 无法连接模型服务，请确认已启动 server/app.py（后端 :8000）。`)
    } finally {
      setThinking(false)
    }
  }

  const newSession = () => {
    const s: ChatSession = {
      id: `${domain.id}-s-${Date.now()}`,
      title: `新对话 ${sessions.length + 1}`,
      model: `${domain.en}-Qwen2.5-3B-v2.1`,
      messages: [],
    }
    setSessions((ss) => [s, ...ss])
    setActiveId(s.id)
  }

  return (
    <div>
      <h1 className="page-title display">模型对话</h1>
      <p className="page-sub">
        加载领域模型权重进行多轮对话测试（FR-13 ~ FR-15）。对话历史与上下文按会话保存，支持连续追问。
      </p>

      <div className="chat-layout">
        <div className="card session-list">
          <div className="nav-label" style={{ padding: '2px 8px 10px' }}>会话列表</div>
          {sessions.map((s) => (
            <div key={s.id} className={`session-item${s.id === activeId ? ' active' : ''}`} onClick={() => setActiveId(s.id)}>
              <b>{s.title}</b>
              <span>{s.messages.length} 轮 · {s.model}</span>
            </div>
          ))}
          <button className="btn ghost sm" style={{ width: '100%', justifyContent: 'center', marginTop: 10 }} onClick={newSession}>
            + 新建会话
          </button>
        </div>

        <div className="card chat-window">
          <div className="chat-head">
            <span className="badge s-运行中" style={{ fontSize: 11 }}>已加载</span>
            <b style={{ fontSize: 13.5 }}>{activeAdapter.name}</b>
            <span style={{ marginLeft: 'auto', display: 'flex', gap: 10, alignItems: 'center' }}>
              <select value={activeAdapter.id ?? ''} onChange={onAdapterChange} style={{ fontSize: 12 }} title="选择领域权重">
                <option value="">基座模型（无微调）</option>
                {adapters.map((a) => <option key={a.id} value={a.id}>{a.name}（loss {Number(a.loss).toFixed(2)}）</option>)}
              </select>
              <span className="rail-meta">{domain.name}领域</span>
            </span>
          </div>

          <div className="chat-log" ref={logRef}>
            {active.messages.length === 0 && (
              <div className="empty">
                <b>开始与 {domain.name}领域模型对话</b>
                上下文将在多轮之间自动保留，可尝试追问细节以检验模型的领域记忆能力。
              </div>
            )}
            {active.messages.map((m, i) => (
              <div key={i} className={`msg ${m.role}`}>
                <div className="who">{m.role === 'user' ? '我' : domain.en.slice(0, 2)}</div>
                <div className="bubble">{m.content}</div>
                <div className="t">{m.time}</div>
              </div>
            ))}
            {thinking && active.messages[active.messages.length - 1]?.role !== 'assistant' && (
              <div className="msg assistant">
                <div className="who">{domain.en.slice(0, 2)}</div>
                <div className="bubble" style={{ background: 'transparent', border: 'none' }}>
                  <span className="typing"><i /><i /><i /></span>
                </div>
              </div>
            )}
          </div>

          <div className="chat-input">
            <textarea
              value={input}
              placeholder={`输入${domain.name}领域问题，Enter 发送…`}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  send()
                }
              }}
            />
            <button className="btn primary" onClick={send} disabled={thinking || !input.trim()}>
              发送
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
