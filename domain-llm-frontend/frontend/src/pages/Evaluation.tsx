import { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import type { Domain, EvalTask } from '../types'
import { EVAL_DIMS } from '../types'
import { getBundle } from '../data/mock'
import StatusBadge from '../components/StatusBadge'
import { RadarChart, ScoreRing } from '../components/charts'

export default function Evaluation() {
  const { domain } = useOutletContext<{ domain: Domain }>()
  const b = getBundle(domain.id)
  const [selected, setSelected] = useState<EvalTask>(b.evals[0])

  const [testSet, setTestSet] = useState(b.datasets[2].name)
  const [submitted, setSubmitted] = useState(false)

  const submit = () => {
    setSubmitted(true)
    setSelected(b.evals[0])
    setTimeout(() => setSubmitted(false), 2600)
  }

  return (
    <div>
      <h1 className="page-title display">模型评测</h1>
      <p className="page-sub">
        选择测试集，基于当前领域模型权重按六个维度自动评测（FR-16 ~ FR-18），生成综合能力评分（FR-19），并可在多领域对比页横向比较（FR-20）。
      </p>

      <div className="grid cols-2">
        <div className="card">
          <h3>配置评测任务</h3>
          <p className="card-sub">FR-16 · 评测任务配置</p>
          <div className="field">
            <label>领域模型 <span className="hint">默认加载最新可用权重，不支持选择</span></label>
            <input value={b.models.find((m) => m.status === '可用')?.name ?? b.models[0].name} readOnly />
          </div>
          <div className="field">
            <label htmlFor="e-set">评测数据 <span className="hint">来自基准测试集的测试划分</span></label>
            <select id="e-set" value={testSet} onChange={(e) => setTestSet(e.target.value)}>
              {b.datasets.map((d) => <option key={d.id}>{d.name} {d.version}</option>)}
            </select>
          </div>
          <div className="field">
            <label>评测维度 <span className="hint">FR-17 · 共 6 项</span></label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {EVAL_DIMS.map((d) => (
                <span key={d} className="badge" style={{ fontSize: 11.5 }}>{d}</span>
              ))}
            </div>
          </div>
          <button className="btn primary" onClick={submit}>启动自动评测</button>
          {submitted && (
            <div className="login-error" style={{ marginTop: 14, background: 'color-mix(in srgb, var(--ok) 7%, white)', borderColor: 'color-mix(in srgb, var(--ok) 30%, white)', color: 'var(--ok)' }}>
              ✓ 评测任务已提交，结果将自动保存至评测记录（FR-18）。
            </div>
          )}
        </div>

        <div className="card">
          <h3>综合能力评分 · {selected.model}</h3>
          <p className="card-sub">FR-19 · 各维度加权综合</p>
          <div className="score-hero">
            <ScoreRing score={selected.composite} />
            <div className="tbl-scroll" style={{ flex: 1, minWidth: 240 }}>
              <table className="tbl dim-table">
                <thead>
                  <tr><th>维度</th><th style={{ width: '45%' }}>得分</th><th>分值</th></tr>
                </thead>
                <tbody>
                  {EVAL_DIMS.map((d, i) => (
                    <tr key={d}>
                      <td>{d}</td>
                      <td><div className="dim-bar"><i style={{ width: `${selected.dims[i]}%` }} /></div></td>
                      <td className="num">{selected.dims[i]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 18 }}>
        <h3>能力画像</h3>
        <p className="card-sub">FR-23 · 评测结果可视化：六维雷达图</p>
        <div style={{ display: 'flex', gap: 32, justifyContent: 'center', alignItems: 'center', flexWrap: 'wrap' }}>
          <RadarChart
            labels={EVAL_DIMS}
            series={[{ name: selected.model, color: 'var(--accent)', values: selected.dims }]}
            size={300}
          />
          <RadarChart
            labels={EVAL_DIMS}
            series={b.evals.slice(0, 3).map((e, i) => ({
              name: e.model,
              color: ['var(--accent)', '#8a99aa', '#c3ccd6'][i],
              values: e.dims,
            }))}
            size={300}
          />
        </div>
        <div style={{ display: 'flex', gap: 18, justifyContent: 'center', flexWrap: 'wrap' }}>
          {b.evals.slice(0, 3).map((e, i) => (
            <span key={e.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 12, color: 'var(--muted)' }}>
              <i style={{ width: 10, height: 10, borderRadius: 2, background: ['var(--accent)', '#8a99aa', '#c3ccd6'][i] }} />
              {e.model} · {e.composite} 分
            </span>
          ))}
        </div>
      </div>

      <div className="card">
        <h3>评测记录</h3>
        <p className="card-sub">FR-18 · 历史评测任务与结果</p>
        <div className="tbl-scroll">
          <table className="tbl">
            <thead>
              <tr><th>评测任务</th><th>模型</th><th>测试集</th><th>状态</th><th>综合评分</th><th>完成时间</th><th /></tr>
            </thead>
            <tbody>
              {b.evals.map((e) => (
                <tr key={e.id} style={{ background: selected.id === e.id ? 'color-mix(in srgb, var(--accent) 5%, white)' : undefined }}>
                  <td className="num" style={{ fontSize: 12.5 }}>{e.id.toUpperCase()}</td>
                  <td style={{ fontWeight: 600 }}>{e.model}</td>
                  <td style={{ fontSize: 12.5, color: 'var(--muted)' }}>{e.testSet}</td>
                  <td><StatusBadge status={e.status} /></td>
                  <td className="num" style={{ fontWeight: 700, color: 'var(--accent)' }}>{e.composite}</td>
                  <td className="num" style={{ fontSize: 12, color: 'var(--muted)' }}>{e.finished}</td>
                  <td><button className="btn ghost sm" onClick={() => setSelected(e)}>查看详情</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
