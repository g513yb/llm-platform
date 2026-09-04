import { Navigate, useNavigate } from 'react-router-dom'
import { useUser } from '../App'
import { DOMAINS, getBundle } from '../data/mock'

const GPUS = [
  { id: 'GPU-01', model: '8GB VRAM', used: 62, task: 'medical-LoRA-r64-e1' },
]

const USERS = [
  { name: 'researcher01', role: '普通用户', domains: '医疗 / 金融', last: '2026-09-01 09:12' },
  { name: 'researcher02', role: '普通用户', domains: '法律', last: '2026-08-31 18:40' },
  { name: 'student05', role: '普通用户', domains: '教育', last: '2026-08-30 21:03' },
  { name: 'admin', role: '管理员', domains: '全部', last: '2026-09-01 08:02' },
]

export default function Admin() {
  const { user } = useUser()
  const nav = useNavigate()
  if (user?.role !== 'admin') return <Navigate to="/" replace />

  return (
    <div className="app-shell" style={{ ['--accent' as string]: '#2447e8' }}>
      <aside className="side">
        <a href="/" className="brand" style={{ textDecoration: 'none' }} onClick={(e) => { e.preventDefault(); nav('/') }}>
          <div className="brand-mark">多</div>
          <div className="brand-name">
            领域大模型工作台
            <small>DOMAIN LLM WORKBENCH</small>
          </div>
        </a>
        <div className="nav-label">系统管理</div>
        <div className="nav-item active"><span className="glyph">⚙</span>平台运行状态</div>
        <div className="nav-item" style={{ cursor: 'pointer' }} onClick={() => nav('/')}><span className="glyph">⌂</span>返回领域选择</div>
        <div className="side-foot">
          <div className="avatar">{user.name[0].toUpperCase()}</div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 600 }}>{user.name}</div>
            <div style={{ fontSize: 11 }}>管理员</div>
          </div>
        </div>
      </aside>

      <div className="main">
        <div className="rail-wrap">
          <div>
            <div className="rail-title"><span className="eyebrow" style={{ color: 'var(--faint)' }}>系统管理</span></div>
            <div className="rail-meta" style={{ marginTop: 4 }}>ADMIN CONSOLE · 2.2.4 / 2.2.6</div>
          </div>
          <div className="rail-meta">平台运行正常 · 全部服务可用</div>
        </div>

        <div className="content">
          <h1 className="page-title display">平台运行状态</h1>
          <p className="page-sub">
            管理员负责 GPU 算力资源、存储空间、用户账户权限与系统配置的维护，并支持平台的领域与模型扩展。
          </p>

          <div className="grid cols-2">
            <div className="card">
              <h3>GPU 算力资源</h3>
              <p className="card-sub">各节点显存占用与当前承载任务</p>
              <div className="grid cols-2" style={{ gap: 14 }}>
                {GPUS.map((g) => (
                  <div key={g.id} className="gpu-card" style={{ border: '1px solid var(--line)', borderRadius: 8, padding: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                      <b className="num" style={{ fontSize: 12.5 }}>{g.id}</b>
                      <span style={{ fontSize: 11, color: 'var(--muted)' }}>{g.model}</span>
                    </div>
                    <div className="bar"><i style={{ width: `${g.used}%`, background: g.used > 85 ? 'var(--err)' : 'var(--accent)' }} /></div>
                    <div className="row"><span>{g.used}% 占用</span><span style={{ color: 'var(--muted)', fontSize: 11 }}>{g.task}</span></div>
                  </div>
                ))}
              </div>
            </div>

            <div className="card">
              <h3>领域资源概览</h3>
              <p className="card-sub">各领域数据集、模型与存储占用 · 2.2.6 支持新增领域</p>
              <div className="tbl-scroll">
                <table className="tbl">
                  <thead>
                    <tr><th>领域</th><th>数据集</th><th>模型</th><th>存储</th></tr>
                  </thead>
                  <tbody>
                    {DOMAINS.map((d) => {
                      const b = getBundle(d.id)
                      const gb = b.models.reduce((a, m) => a + m.sizeGB, 0).toFixed(1)
                      return (
                        <tr key={d.id}>
                          <td>
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontWeight: 600 }}>
                              <i style={{ width: 9, height: 9, borderRadius: 2, background: d.accent }} />{d.name}领域
                            </span>
                          </td>
                          <td className="num">{b.datasets.length}</td>
                          <td className="num">{b.models.length}</td>
                          <td className="num">{gb} GB</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <button className="btn ghost sm" style={{ marginTop: 14 }}>+ 接入新领域</button>
            </div>
          </div>

          <div className="grid cols-2" style={{ marginTop: 18 }}>
            <div className="card">
              <h3>用户与权限</h3>
              <p className="card-sub">2.2.4 · 身份认证与权限控制</p>
              <div className="tbl-scroll">
                <table className="tbl">
                  <thead>
                    <tr><th>用户</th><th>角色</th><th>可见领域</th><th>最近登录</th></tr>
                  </thead>
                  <tbody>
                    {USERS.map((u) => (
                      <tr key={u.name}>
                        <td className="num" style={{ fontSize: 12.5 }}>{u.name}</td>
                        <td><span className={`badge${u.role === '管理员' ? ' s-运行中' : ''}`}>{u.role}</span></td>
                        <td style={{ fontSize: 12.5 }}>{u.domains}</td>
                        <td className="num" style={{ fontSize: 12, color: 'var(--muted)' }}>{u.last}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="card">
              <h3>系统配置</h3>
              <p className="card-sub">关键参数 · 修改即时生效</p>
              <div className="field">
                <label htmlFor="a-max">单用户并发训练任务上限</label>
                <input id="a-max" className="num" defaultValue="2" />
              </div>
              <div className="field">
                <label htmlFor="a-ret">评测结果保留期（天）</label>
                <input id="a-ret" className="num" defaultValue="180" />
              </div>
              <div className="field">
                <label htmlFor="a-new">默认开放领域注册</label>
                <select id="a-new" defaultValue="开启">
                  <option>开启</option><option>关闭</option>
                </select>
              </div>
              <button className="btn primary sm">保存配置</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
