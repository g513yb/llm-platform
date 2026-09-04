import { Link, NavLink, Outlet, useParams } from 'react-router-dom'
import { getDomain } from '../data/mock'
import { useUser } from '../App'
import PipelineRail from '../components/PipelineRail'

const NAV = [
  { to: '', label: '工作台概览', glyph: '◫', end: true },
  { to: 'datasets', label: '数据集管理', glyph: '▤' },
  { to: 'training', label: '模型训练', glyph: '⧗' },
  { to: 'chat', label: '模型对话', glyph: '◍' },
  { to: 'evaluation', label: '模型评测', glyph: '◎' },
]

export default function Workspace() {
  const { domainId } = useParams()
  const domain = getDomain(domainId)
  const { user, logout } = useUser()

  return (
    <div className="app-shell" style={{ ['--accent' as string]: domain.accent }}>
      <aside className="side">
        <Link to="/" className="brand" style={{ textDecoration: 'none' }}>
          <div className="brand-mark">域</div>
          <div className="brand-name">
            领域大模型工作台
            <small>DOMAIN LLM WORKBENCH</small>
          </div>
        </Link>

        <div className="domain-chip">
          <span className="dot" />
          <b>{domain.name}领域</b>
          <span>{domain.en}</span>
        </div>

        <div className="nav-label">工作流模块</div>
        {NAV.map((n) => (
          <NavLink
            key={n.to}
            to={n.to ? `/domain/${domain.id}/${n.to}` : `/domain/${domain.id}`}
            end={n.end}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          >
            <span className="glyph">{n.glyph}</span>
            {n.label}
          </NavLink>
        ))}

        <div className="nav-label">跨领域</div>
        <NavLink to="/compare" className="nav-item">
          <span className="glyph">⇄</span>多领域对比
        </NavLink>
        {user?.role === 'admin' && (
          <NavLink to="/admin" className="nav-item">
            <span className="glyph">⚙</span>系统管理
          </NavLink>
        )}
        <NavLink to="/" className="nav-item">
          <span className="glyph">⌂</span>切换领域
        </NavLink>

        <div className="side-foot">
          <div className="avatar">{user?.name?.[0]?.toUpperCase() ?? 'U'}</div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 600 }}>{user?.name}</div>
            <div style={{ fontSize: 11 }}>{user?.role === 'admin' ? '管理员' : '普通用户'}</div>
          </div>
          <button className="btn ghost sm" style={{ marginLeft: 'auto' }} onClick={logout}>退出</button>
        </div>
      </aside>

      <div className="main">
        <PipelineRail domainId={domain.id} title={`${domain.name}领域工作空间`} />
        <div className="content">
          <Outlet context={{ domain }} />
        </div>
      </div>
    </div>
  )
}
