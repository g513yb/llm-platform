import { useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import type { Domain, TaskStatus } from '../types'
import { EVAL_DIMS } from '../types'
import StatusBadge from '../components/StatusBadge'
import { RadarChart, ScoreRing } from '../components/charts'

const API_BASE = import.meta.env.VITE_API_BASE || ''

interface Adapter {
  id: string
  name: string
  domain: string
  created_at: string
}

interface EvalJob {
  id: string
  name: string
  status: TaskStatus
  progress: number
  message: string
  adapter: string
  adapterId: string | null
  use_cot: boolean
  total: number
  correct: number
  overall: number
  composite: number
  n_shot: number
  started: string
}

interface EvalResult {
  task_id: string
  adapter: string
  use_cot: boolean
  composite: number
  result: {
    overall: number
    correct: number
    total: number
    per_category: Record<string, number>
    per_subcategory: Record<string, Record<string, number>>
    wrong_items: Array<{ id: number; exam_type: string; exam_class: string; question_type: string; gold: string; pred: string }>
    wrong_truncated: boolean
  }
  finished_at: string
}

export default function Evaluation() {
  const { domain } = useOutletContext<{ domain: Domain }>()
  const [adapters, setAdapters] = useState<Adapter[]>([])
  const [jobs, setJobs] = useState<EvalJob[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [result, setResult] = useState<EvalResult | null>(null)
  const [errMsg, setErrMsg] = useState('')
  const [form, setForm] = useState({
    adapterId: '',
    useCot: true,
    batchSize: '4',
    nShot: '0',
    name: '',
  })

  const refreshAdapters = async () => {
    try {
      const list = await fetch(`${API_BASE}/api/adapters`).then((x) => x.json())
      if (Array.isArray(list)) setAdapters(list)
    } catch { /* ignore */ }
  }

  const refreshJobs = async () => {
    try {
      const list = await fetch(`${API_BASE}/api/eval/jobs`).then((x) => x.json())
      if (Array.isArray(list)) setJobs(list)
    } catch { /* ignore */ }
  }

  useEffect(() => {
    refreshAdapters()
    refreshJobs()
    const t = setInterval(refreshJobs, 2000)
    return () => clearInterval(t)
  }, [])

  const loadResult = async (id: string) => {
    try {
      const r = await fetch(`${API_BASE}/api/eval/${id}/result`).then((x) => x.json())
      if (r.error) { setErrMsg(r.error); return }
      setResult(r)
      setSelectedId(id)
      setErrMsg('')
    } catch {
      setErrMsg('获取结果失败')
    }
  }

  const submit = async () => {
    setErrMsg('')
    const nShotNum = Number(form.nShot)
    if (!Number.isInteger(nShotNum) || nShotNum < 0 || nShotNum > 10) {
      setErrMsg('Few-shot 数必须为 0-10 的整数')
      return
    }
    const adapterId = form.adapterId || null
    try {
      await fetch(`${API_BASE}/api/adapters/load`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ adapterId }),
      })
    } catch { /* ignore */ }
    try {
      const r = await fetch(`${API_BASE}/api/eval`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name.trim() || undefined,
          adapterId,
          use_cot: form.useCot,
          batchSize: Number(form.batchSize) || 1,
          nShot: Number(form.nShot) || 0,
        }),
      }).then((x) => x.json())
      if (r.error) { setErrMsg(r.error); return }
      await refreshJobs()
    } catch {
      setErrMsg('启动评测失败：无法连接后端')
    }
  }

  const stopTask = async (id: string) => {
    try { await fetch(`${API_BASE}/api/eval/${id}/stop`, { method: 'POST' }); await refreshJobs() } catch { /* ignore */ }
  }

  const deleteTask = async (id: string) => {
    try {
      await fetch(`${API_BASE}/api/eval/${id}`, { method: 'DELETE' })
      await refreshJobs()
      if (selectedId === id) { setSelectedId(null); setResult(null) }
    } catch { /* ignore */ }
  }

  const selected = jobs.find((j) => j.id === selectedId)
  const dims = selected ? Array(6).fill(selected.composite) : Array(6).fill(0)
  const running = jobs.some((j) => j.status === '运行中' || j.status === '等待')

  return (
    <div>
      <h1 className="page-title display">模型评测</h1>
      <p className="page-sub">
        基于 CMB 医师考试选择题测试集（11200 题）评测领域模型准确率，按 exam_type/exam_class 分层统计，支持 CoT/直接两种 prompt 模式。
      </p>

      <div className="grid cols-2">
        <div className="card">
          <h3>配置评测任务</h3>
          <p className="card-sub">CMB-Exam · 11200 道选择题 · 分层准确率</p>
          <div className="field">
            <label htmlFor="e-adapter">领域权重 <span className="hint">选择要评测的 LoRA 权重，空为基座模型</span></label>
            <select id="e-adapter" value={form.adapterId} onChange={(e) => setForm({ ...form, adapterId: e.target.value })}>
              <option value="">基座模型（无 LoRA）</option>
              {adapters.filter((a) => a.domain === domain.name).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </div>
          <div className="field">
            <label>评测数据 <span className="hint">固定 CMB-test 选择题测试集</span></label>
            <input value="CMB-Exam · CMB-test-choice-question-merge（11200 题）" readOnly style={{ fontSize: 12.5 }} />
          </div>
          <div className="field">
            <label htmlFor="e-name">任务名称 <span className="hint">可选，留空自动生成</span></label>
            <input id="e-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder={`评测-${domain.name}`} />
          </div>
          <div className="grid cols-2" style={{ gap: 12 }}>
            <div className="field">
              <label htmlFor="e-cot">Prompt 模式</label>
              <select id="e-cot" value={form.useCot ? 'cot' : 'direct'} onChange={(e) => setForm({ ...form, useCot: e.target.value === 'cot' })}>
                <option value="cot">CoT（分析后给答案）</option>
                <option value="direct">直接输出选项</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="e-batch">批大小</label>
              <input id="e-batch" className="num" value={form.batchSize} onChange={(e) => setForm({ ...form, batchSize: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="e-nshot">Few-shot 数 <span className="hint">0-10 整数，0=zero-shot，从 CMB-val 按 exam_type/class 选例</span></label>
              <input id="e-nshot" className="num" type="number" min={0} max={10} step={1} value={form.nShot} onChange={(e) => setForm({ ...form, nShot: e.target.value })} />
            </div>
          </div>
          <div className="field">
            <label>评测维度 <span className="hint">当前以准确率填充，其余维度后续接入</span></label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {EVAL_DIMS.map((d) => <span key={d} className="badge" style={{ fontSize: 11.5 }}>{d}</span>)}
            </div>
          </div>
          <button className="btn primary" onClick={submit} disabled={running}>启动评测</button>
          {running && <span style={{ marginLeft: 10, fontSize: 12, color: 'var(--muted)' }}>有任务运行中…</span>}
          {errMsg && <div className="login-error" style={{ marginTop: 10 }}>{errMsg}</div>}
        </div>

        <div className="card">
          <h3>综合评分{selected ? ` · ${selected.name}` : ''}</h3>
          <p className="card-sub">准确率映射 0-100 综合分</p>
          {selected ? (
            <>
              <div className="score-hero">
                <ScoreRing score={selected.composite} />
                <div className="tbl-scroll" style={{ flex: 1, minWidth: 240 }}>
                  <table className="tbl dim-table">
                    <thead><tr><th>维度</th><th style={{ width: '45%' }}>得分</th><th>分值</th></tr></thead>
                    <tbody>
                      {EVAL_DIMS.map((d, i) => (
                        <tr key={d}><td>{d}</td><td><div className="dim-bar"><i style={{ width: `${dims[i]}%` }} /></div></td><td className="num">{dims[i]}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              <div style={{ marginTop: 14, display: 'flex', gap: 18, fontSize: 12.5, color: 'var(--muted)' }}>
                <span>准确率：<b style={{ color: 'var(--accent)' }}>{(selected.overall * 100).toFixed(2)}%</b></span>
                <span>正确/总数：<b>{selected.correct}/{selected.total}</b></span>
                <span>权重：{selected.adapter}</span>
              </div>
            </>
          ) : (
            <div className="empty" style={{ padding: '20px 0' }}><b>暂无选中评测</b>启动评测后，从下方记录点击"查看详情"。</div>
          )}
        </div>
      </div>

      {result && (
        <div className="card" style={{ marginTop: 18 }}>
          <h3>分层准确率 · {result.task_id}</h3>
          <p className="card-sub">按 exam_type → exam_class 二级聚合，父类为子类算术平均</p>
          <div className="tbl-scroll">
            <table className="tbl">
              <thead><tr><th>exam_type</th><th>exam_class</th><th style={{ width: 120 }}>准确率</th></tr></thead>
              <tbody>
                {Object.entries(result.result.per_subcategory).flatMap(([et, classes]) =>
                  Object.entries(classes).map(([ec, acc]) => (
                    <tr key={`${et}-${ec}`}><td>{et}</td><td style={{ fontSize: 12.5, color: 'var(--muted)' }}>{ec}</td><td className="num" style={{ fontWeight: 700, color: 'var(--accent)' }}>{(acc * 100).toFixed(2)}%</td></tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <div style={{ marginTop: 14, display: 'flex', gap: 18, fontSize: 12.5, color: 'var(--muted)', flexWrap: 'wrap' }}>
            <span>父类平均：</span>
            {Object.entries(result.result.per_category).map(([et, acc]) => (
              <span key={et}>{et} <b style={{ color: 'var(--accent)' }}>{(acc * 100).toFixed(2)}%</b></span>
            ))}
          </div>
          {result.result.wrong_items.length > 0 && (
            <>
              <h4 style={{ marginTop: 18 }}>错题示例{result.result.wrong_truncated ? '（前 200 条）' : ''}</h4>
              <div className="tbl-scroll">
                <table className="tbl">
                  <thead><tr><th>id</th><th>exam_type</th><th>exam_class</th><th>题型</th><th>标准答案</th><th>模型答案</th></tr></thead>
                  <tbody>
                    {result.result.wrong_items.map((w) => (
                      <tr key={w.id}><td className="num">{w.id}</td><td>{w.exam_type}</td><td style={{ fontSize: 12.5, color: 'var(--muted)' }}>{w.exam_class}</td><td style={{ fontSize: 12 }}>{w.question_type}</td><td className="num">{w.gold}</td><td className="num" style={{ color: 'var(--err)' }}>{w.pred || '（空）'}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      <div className="card">
        <h3>评测记录</h3>
        <p className="card-sub">历史评测任务与结果</p>
        <div className="tbl-scroll">
          <table className="tbl">
            <thead><tr><th>任务</th><th>权重</th><th>模式</th><th>shot</th><th>状态</th><th style={{ width: 180 }}>进度</th><th>综合评分</th><th>启动时间</th><th style={{ width: 140 }}>操作</th></tr></thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id} style={{ background: selectedId === j.id ? 'color-mix(in srgb, var(--accent) 5%, white)' : undefined }}>
                  <td style={{ fontSize: 12.5 }}>{j.name}</td>
                  <td style={{ fontSize: 12.5, color: 'var(--muted)' }}>{j.adapter}</td>
                  <td style={{ fontSize: 12 }}>{j.use_cot ? 'CoT' : '直接'}</td>
                  <td className="num" style={{ fontSize: 12 }}>{j.n_shot || 0}</td>
                  <td><StatusBadge status={j.status} /></td>
                  <td>
                    {j.status === '完成' ? (
                      <span style={{ color: 'var(--ok)', fontSize: 12.5, fontWeight: 600 }}>✓ 100%</span>
                    ) : j.status === '运行中' || j.status === '等待' ? (
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <div className="progress"><i style={{ width: `${j.progress}%` }} /></div>
                        <span className="num" style={{ fontSize: 11, color: 'var(--muted)' }}>{j.progress}%</span>
                      </div>
                    ) : <span style={{ fontSize: 12, color: 'var(--faint)' }}>—</span>}
                  </td>
                  <td className="num" style={{ fontWeight: 700, color: 'var(--accent)' }}>{j.composite || '—'}</td>
                  <td className="num" style={{ fontSize: 12, color: 'var(--muted)' }}>{j.started}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 6 }}>
                      {j.status === '完成' && <button className="btn ghost sm" onClick={() => loadResult(j.id)}>查看详情</button>}
                      {(j.status === '运行中' || j.status === '等待') && <button className="btn" style={{ fontSize: 11, padding: '2px 8px' }} onClick={() => stopTask(j.id)}>终止</button>}
                      {(j.status === '完成' || j.status === '失败' || j.status === '已终止') && <button className="btn" style={{ fontSize: 11, padding: '2px 8px', color: 'var(--err)' }} onClick={() => deleteTask(j.id)}>删除</button>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {jobs.length === 0 && <div className="empty" style={{ padding: '16px 0', textAlign: 'center' }}>暂无评测任务</div>}
        </div>
        {jobs.filter((j) => j.status === '失败' || j.status === '已终止').map((j) => (
          <div key={j.id} className="login-error" style={{ marginTop: 14 }}>
            任务 <b>{j.name}</b> {j.status === '已终止' ? '已终止' : '失败'}：{j.message || '详情未知'}
          </div>
        ))}
      </div>
    </div>
  )
}
