import { Link, useNavigate } from 'react-router-dom'
import { DOMAINS, getBundle } from '../data/mock'

export default function DomainSelect() {
  const nav = useNavigate()

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 22 }}>
        <div className="brand">
          <div className="brand-mark">域</div>
          <div className="brand-name">
            领域大模型训练与评测平台
            <small>DOMAIN LLM WORKBENCH</small>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <button className="btn ghost sm" onClick={() => nav('/compare')}>多领域对比</button>
          <button className="btn ghost sm" onClick={() => nav('/admin')}>系统管理</button>
        </div>
      </header>

      <div className="domain-hero">
        <div className="eyebrow" style={{ color: 'var(--faint)' }}>FR-01 · 领域选择</div>
        <h1 className="display">选择目标领域，进入工作空间</h1>
        <p>
          每个领域拥有独立的数据集、模型、训练任务与评测记录。
          完成选择后，你将进入该领域的工作流：数据处理 → 模型训练 → 对话测试 → 效果评测。
        </p>
        <div className="legend">
          {DOMAINS.map((d) => (
            <span key={d.id}><i style={{ background: d.accent }} />{d.name}</span>
          ))}
        </div>
      </div>

      <div className="domain-grid">
        {DOMAINS.map((d) => {
          const b = getBundle(d.id)
          const best = Math.max(...b.evals.map((e) => e.composite))
          return (
            <Link
              key={d.id}
              to={`/domain/${d.id}`}
              className="domain-card"
              style={{ ['--dc' as string]: d.accent }}
            >
              <span className="enter">进入 →</span>
              <div className="en">{d.en} · FR-02</div>
              <h2>{d.name}领域</h2>
              <div className="tagline">{d.tagline}</div>
              <p>{d.description}</p>
              <div className="stats">
                <div><b className="num">{b.datasets.length}</b>数据集</div>
                <div><b className="num">{b.models.length}</b>领域模型</div>
                <div><b className="num">{b.tasks.length}</b>训练任务</div>
                <div><b className="num" style={{ color: d.accent }}>{best}</b>综合评分</div>
              </div>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
