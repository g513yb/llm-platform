import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { DOMAINS, getBundle } from '../data/mock'
import { EVAL_DIMS } from '../types'
import { RadarChart } from '../components/charts'

export default function Compare() {
  const nav = useNavigate()
  const [on, setOn] = useState<string[]>(DOMAINS.map((d) => d.id))

  const active = DOMAINS.filter((d) => on.includes(d.id))
  const rows = active
    .map((d) => {
      const best = [...getBundle(d.id).evals].sort((a, b) => b.composite - a.composite)[0]
      return { domain: d, eval: best }
    })
    .sort((a, b) => b.eval.composite - a.eval.composite)

  const maxScore = 100

  return (
    <div className="app-shell" style={{ ['--accent' as string]: '#2447e8' }}>
      <aside className="side">
        <a href="/" className="brand" style={{ textDecoration: 'none' }} onClick={(e) => { e.preventDefault(); nav('/') }}>
          <div className="brand-mark">域</div>
          <div className="brand-name">
            领域大模型工作台
            <small>DOMAIN LLM WORKBENCH</small>
          </div>
        </a>
        <div className="nav-label">跨领域分析</div>
        <div className="nav-item active"><span className="glyph">⇄</span>多领域对比</div>
        <div className="nav-item" style={{ cursor: 'pointer' }} onClick={() => nav('/')}><span className="glyph">⌂</span>返回领域选择</div>

      </aside>

      <div className="main">
        <div className="rail-wrap">
          <div>
            <div className="rail-title"><span className="eyebrow" style={{ color: 'var(--faint)' }}>多领域结果比较</span></div>
            <div className="rail-meta" style={{ marginTop: 4 }}>FR-20 · CROSS-DOMAIN COMPARISON</div>
          </div>
          <div className="rail-meta">各领域取最佳模型的评测结果</div>
        </div>

        <div className="content">
          <h1 className="page-title display">多领域模型能力对比</h1>
          <p className="page-sub">
            选择参与对比的领域，查看各领域最佳模型在六个评测维度上的表现与综合评分差异。
          </p>

          <div className="cmp-chips">
            {DOMAINS.map((d) => {
              const onIt = on.includes(d.id)
              return (
                <button
                  key={d.id}
                  className={`cmp-chip${onIt ? ' on' : ''}`}
                  style={{ ['--cc' as string]: d.accent }}
                  onClick={() => setOn((s) => (onIt ? s.filter((x) => x !== d.id) : [...s, d.id]))}
                  aria-pressed={onIt}
                >
                  <i />{d.name}领域
                </button>
              )
            })}
          </div>

          {rows.length === 0 ? (
            <div className="card empty"><b>尚未选择领域</b>请至少选择一个领域参与对比。</div>
          ) : (
            <>
              <div className="card">
                <h3>综合评分排名</h3>
                <p className="card-sub">FR-19 / FR-20 · 按综合能力评分排序</p>
                <div className="cmp-bars">
                  {rows.map((r, i) => (
                    <div className="cmp-bar-row" key={r.domain.id}>
                      <div className="nm">{r.domain.name}</div>
                      <div className="cmp-bar-track">
                        <div className="cmp-bar-fill" style={{ width: `${(r.eval.composite / maxScore) * 100}%`, ['--bc' as string]: r.domain.accent }}>
                          {r.eval.composite}
                        </div>
                      </div>
                      <div className="rank">
                        RANK {i + 1} · {r.eval.model}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="card" style={{ marginTop: 18 }}>
                <h3>能力维度雷达对比</h3>
                <p className="card-sub">各领域模型在六个评测维度上的表现叠加</p>
                <div style={{ display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: 28 }}>
                  <RadarChart
                    labels={EVAL_DIMS}
                    series={rows.map((r) => ({ name: r.domain.name, color: r.domain.accent, values: r.eval.dims }))}
                    size={330}
                  />
                </div>
                <div style={{ display: 'flex', gap: 20, justifyContent: 'center', flexWrap: 'wrap' }}>
                  {rows.map((r) => (
                    <span key={r.domain.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 12.5, color: 'var(--muted)' }}>
                      <i style={{ width: 10, height: 10, borderRadius: 2, background: r.domain.accent }} />
                      {r.domain.name}领域 · {r.eval.model} · {r.eval.composite} 分
                    </span>
                  ))}
                </div>
              </div>

              <div className="card" style={{ marginTop: 18 }}>
                <h3>维度明细</h3>
                <p className="card-sub">各领域在每一评测维度的得分</p>
                <div className="tbl-scroll">
                  <table className="tbl">
                    <thead>
                      <tr>
                        <th>领域 / 模型</th>
                        {EVAL_DIMS.map((d) => <th key={d} style={{ textAlign: 'right' }}>{d}</th>)}
                        <th style={{ textAlign: 'right' }}>综合</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r) => (
                        <tr key={r.domain.id}>
                          <td>
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                              <i style={{ width: 9, height: 9, borderRadius: 2, background: r.domain.accent }} />
                              <b>{r.domain.name}领域</b>
                              <span className="num" style={{ fontSize: 11, color: 'var(--faint)' }}>{r.eval.model}</span>
                            </span>
                          </td>
                          {r.eval.dims.map((v, i) => (
                            <td key={i} className="num" style={{ textAlign: 'right' }}>{v}</td>
                          ))}
                          <td className="num" style={{ textAlign: 'right', fontWeight: 700, color: r.domain.accent }}>{r.eval.composite}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
