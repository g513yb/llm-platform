import { FormEvent, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useUser } from '../App'

export default function Login() {
  const { login } = useUser()
  const nav = useNavigate()
  const loc = useLocation() as { state?: { from?: string } }
  const [name, setName] = useState('')
  const [pwd, setPwd] = useState('')
  const [err, setErr] = useState('')

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !pwd.trim()) {
      setErr('请输入用户名和密码。')
      return
    }
    if (pwd.trim().length < 4) {
      setErr('密码至少 4 位，请重新输入。')
      return
    }
    const isAdmin = name.trim() === 'admin'
    login({ name: name.trim(), role: isAdmin ? 'admin' : 'user' })
    nav(loc.state?.from ?? '/', { replace: true })
  }

  return (
    <div className="login-page">
      <form className="card login-card" onSubmit={submit} noValidate>
        <div className="login-brand">
          <div className="brand-mark" style={{ margin: '0 auto', width: 40, height: 40, fontSize: 19 }}>域</div>
          <h1>领域大模型训练与评测平台</h1>
          <p>Domain LLM Training &amp; Evaluation Workbench</p>
        </div>
        {err && <div className="login-error" role="alert">{err}</div>}
        <div className="field">
          <label htmlFor="login-name">用户名</label>
          <input id="login-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="user 或 admin" autoComplete="username" />
        </div>
        <div className="field">
          <label htmlFor="login-pwd">密码</label>
          <input id="login-pwd" type="password" value={pwd} onChange={(e) => setPwd(e.target.value)} placeholder="至少 4 位" autoComplete="current-password" />
        </div>
        <button className="btn primary" style={{ width: '100%', justifyContent: 'center' }} type="submit">
          登录平台
        </button>
        <div className="login-hint">
          演示账号：<code>user / user</code>（普通用户）　<code>admin / admin</code>（管理员）
        </div>
      </form>
    </div>
  )
}
