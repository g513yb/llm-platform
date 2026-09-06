import { useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import type { Domain, TrainTask, TaskStatus } from '../types'
import { BASE_MODEL, MODEL_PATH, FINETUNE_METHOD, QUANT_BITS } from '../data/mock'
import StatusBadge from '../components/StatusBadge'
import { LossCurve } from '../components/charts'

const API_BASE = import.meta.env.VITE_API_BASE || ''

const mapJob = (j: Record<string, unknown>): TrainTask => ({
  id: (j.id as string) || '',
  name: (j.name as string) || '',
  baseModel: (j.baseModel as string) || BASE_MODEL,
  dataset: (j.dataset as string) || '',
  status: (j.status as TaskStatus) || '等待',
  progress: (j.progress as number) || 0,
  loss: (j.loss as number) || 0,
  evalLoss: 0,
  started: (j.started as string) || '',
  curve: (j.loss_history as number[]) || [],
  message: (j.message as string) || '',
  domain: (j.domain as string) || '',
})

export default function Training() {
  const { domain } = useOutletContext<{ domain: Domain }>()
  const [tasks, setTasks] = useState<TrainTask[]>([])
  const [created, setCreated] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [health, setHealth] = useState<{ model: string; quant: string }>({ model: BASE_MODEL, quant: QUANT_BITS })
  const [modelList, setModelList] = useState<{ name: string; path: string }[]>([])
  const [trainDataset] = useState<{ datasetId: string; label: string; source: string } | null>(() => {
    try {
      const raw = sessionStorage.getItem(`train-dataset:${domain.id}`)
      return raw ? JSON.parse(raw) : null
    } catch { return null }
  })
  const [errMsg, setErrMsg] = useState('')

  const [form, setForm] = useState({
    name: `${domain.en}-LoRA-r16-e3`,
    datasetId: trainDataset?.datasetId || '',
    modelPath: MODEL_PATH,
    rank: '16',
    lr: '2e-4',
    epochs: '3',
    batch: '8',
  })

  const refreshJobs = async () => {
    try {
      const list = await fetch(`${API_BASE}/api/train/jobs`).then((x) => x.json())
      if (Array.isArray(list)) setTasks(list.map(mapJob))
    } catch { /* 忽略瞬时错误 */ }
  }

  useEffect(() => {
    fetch(`${API_BASE}/api/health`).then((x) => x.json()).then((h) => {
      if (h.model) setHealth({ model: h.model, quant: h.quant || QUANT_BITS })
    }).catch(() => {})
    fetch(`${API_BASE}/api/models`).then((x) => x.json()).then((m) => {
      if (Array.isArray(m.models)) {
        setModelList(m.models)
        if (m.current) setForm((f) => ({ ...f, modelPath: m.current }))
      }
    }).catch(() => {})
    refreshJobs()
    const t = setInterval(refreshJobs, 2000)
    return () => clearInterval(t)
  }, [])


  const create = async () => {
    if (!form.name.trim()) return
    if (!form.datasetId) { setErrMsg('请先到数据集管理页选择数据集'); return }
    const lrNum = parseFloat(form.lr)
    if (isNaN(lrNum) || lrNum <= 0) { setErrMsg('学习率必须为正数'); return }
    const epochsNum = parseInt(form.epochs)
    if (isNaN(epochsNum) || epochsNum < 1) { setErrMsg('训练轮数须为 ≥1 的整数'); return }
    const batchNum = parseInt(form.batch)
    if (isNaN(batchNum) || batchNum < 1) { setErrMsg('批大小须为 ≥1 的整数'); return }
    setErrMsg('')
    setSubmitting(true)
    const taskName = form.name.trim()
    const datasetLabel = trainDataset?.label || '本地数据集'
    setCreated(true)
    setTimeout(() => setCreated(false), 3000)

    try {
      const r = await fetch(`${API_BASE}/api/train`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: taskName,
          datasetId: form.datasetId,
          datasetLabel,
          modelPath: form.modelPath.trim(),
          domain: domain.name,
          rank: Number(form.rank),
          lr: form.lr,
          epochs: Number(form.epochs),
          batch: Number(form.batch),
        }),
      }).then((x) => x.json())
      if (r.error) { setErrMsg(r.error as string); return }
      await refreshJobs()
    } catch {
      setErrMsg('启动训练失败：无法连接本地服务')
    } finally {
      setSubmitting(false)
    }
  }

  const stopTask = async (id: string) => {
    try {
      await fetch(`${API_BASE}/api/train/${id}/stop`, { method: 'POST' })
      await refreshJobs()
    } catch { /* ignore */ }
  }

  const deleteTask = async (id: string) => {
    try {
      await fetch(`${API_BASE}/api/train/${id}`, { method: 'DELETE' })
      await refreshJobs()
    } catch { /* ignore */ }
  }

  const visibleTasks = tasks.filter((t) => !t.domain || t.domain === domain.name)
  const latest = visibleTasks[0]

  return (
    <div>
      <h1 className="page-title display">模型训练</h1>
      <p className="page-sub">
        基于基座模型 {health.model}（LoRA · {health.quant} 量化，模型/量化由后端配置驱动），选择数据集版本并调整超参数创建训练任务。任务在后台执行（FR-09 ~ FR-12），完成后领域权重自动入库。
      </p>

      <div className="grid cols-2">
        {/* 新建任务 */}
        <div className="card">
          <h3>创建微调任务</h3>
          <p className="card-sub">FR-09 · 模型及训练参数配置 ／ FR-10 · 任务创建</p>
          <div className="field">
            <label htmlFor="t-name">任务名称</label>
            <input id="t-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="t-path">基础模型 <span className="hint">从已下载模型中选择</span></label>
            {modelList.length > 0 ? (
              <select id="t-path" value={form.modelPath} onChange={(e) => setForm({ ...form, modelPath: e.target.value })}>
                {modelList.map((m) => (
                  <option key={m.path} value={m.path}>{m.name}</option>
                ))}
              </select>
            ) : (
              <input id="t-path" value={form.modelPath} placeholder="加载中…" readOnly />
            )}
          </div>
          <div className="field">
            <label>数据集 <span className="hint">由数据集管理页选定</span></label>
            {trainDataset ? (
              <input value={trainDataset.label} readOnly style={{ fontSize: 12.5 }} />
            ) : (
              <span style={{ fontSize: 12, color: 'var(--muted)' }}>请先到「数据集管理」选择数据集（文件导入或参考数据集）</span>
            )}
          </div>
          <div className="grid cols-2" style={{ gap: 12 }}>
            <div className="field">
              <label>微调方法 <span className="hint">固定，不支持选择</span></label>
              <input value={`${FINETUNE_METHOD} · ${health.quant} 量化`} readOnly />
            </div>
            <div className="field">
              <label htmlFor="t-rank">秩 (r)</label>
              <select id="t-rank" value={form.rank} onChange={(e) => setForm({ ...form, rank: e.target.value })}>
                <option>8</option><option>16</option><option>32</option><option>64</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="t-lr">学习率</label>
              <input id="t-lr" className="num" value={form.lr} onChange={(e) => setForm({ ...form, lr: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="t-epoch">训练轮数</label>
              <input id="t-epoch" className="num" value={form.epochs} onChange={(e) => setForm({ ...form, epochs: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="t-batch">批大小</label>
              <input id="t-batch" className="num" value={form.batch} onChange={(e) => setForm({ ...form, batch: e.target.value })} />
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button className="btn primary" onClick={create} disabled={submitting}>{submitting ? '启动中…' : '启动训练任务'}</button>
            {created && <span style={{ color: 'var(--ok)', fontSize: 12.5, fontWeight: 600 }}>✓ 任务已加入队列</span>}
          </div>
          {errMsg && <div className="login-error" style={{ marginTop: 10 }}>{errMsg}</div>}
        </div>

        {/* 训练结果 */}
        <div className="card">
          <h3>训练结果{latest ? ` · ${latest.name}` : ''}</h3>
          <p className="card-sub">FR-22 · 训练结果展示：损失曲线收敛情况（实时）</p>
          {latest && latest.curve.length > 0 ? (
            <LossCurve points={latest.curve} color="var(--accent)" />
          ) : (
            <div className="empty" style={{ padding: '20px 0' }}><b>等待训练开始</b>启动训练后，损失曲线将在此实时绘制。</div>
          )}
          <div style={{ display: 'flex', gap: 26, marginTop: 14 }}>
            <div>
              <div className="eyebrow" style={{ color: 'var(--faint)' }}>当前 LOSS</div>
              <div className="num" style={{ fontSize: 21, fontWeight: 700 }}>{latest ? latest.loss.toFixed(2) : '—'}</div>
            </div>
            <div>
              <div className="eyebrow" style={{ color: 'var(--faint)' }}>进度</div>
              <div className="num" style={{ fontSize: 21, fontWeight: 700 }}>{latest ? `${latest.progress}%` : '—'}</div>
            </div>
            <div>
              <div className="eyebrow" style={{ color: 'var(--faint)' }}>基座模型</div>
              <div style={{ fontSize: 13, marginTop: 6, fontWeight: 600 }}>
                {health.model} <span className="badge" style={{ marginLeft: 6 }}>LoRA·{health.quant}</span>
              </div>
            </div>
          </div>
          {latest && latest.status === '完成' && (
            <div style={{ marginTop: 12, fontSize: 12.5, color: 'var(--ok)', background: 'color-mix(in srgb, var(--ok) 8%, white)', padding: '8px 12px', borderRadius: 8 }}>
              ✓ 权重已入库，可前往「对话」页加载该权重推理，或在「评测」页发起评测。
            </div>
          )}
        </div>
      </div>

      {/* 任务列表 */}
      <div className="card">
        <h3>训练任务列表</h3>
        <p className="card-sub">FR-11 · 任务状态：等待 / 运行中 / 完成 / 失败 / 已终止</p>
        <div className="tbl-scroll">
          <table className="tbl">
            <thead>
              <tr><th>任务</th><th>基础模型</th><th>数据集版本</th><th>状态</th><th style={{ width: 180 }}>进度</th><th>启动时间</th><th style={{ width: 120 }}>操作</th></tr>
            </thead>
            <tbody>
              {visibleTasks.map((t) => (
                <tr key={t.id}>
                  <td className="num" style={{ fontSize: 12.5 }}>{t.name}</td>
                  <td>{t.baseModel}</td>
                  <td style={{ fontSize: 12.5, color: 'var(--muted)' }}>{t.dataset}</td>
                  <td><StatusBadge status={t.status} /></td>
                  <td>
                    {t.status === '完成' ? (
                      <span style={{ color: 'var(--ok)', fontSize: 12.5, fontWeight: 600 }}>✓ 100% · loss {t.loss.toFixed(2)}</span>
                    ) : t.status === '运行中' || t.status === '等待' ? (
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <div className="progress"><i style={{ width: `${t.progress}%` }} /></div>
                        <span className="num" style={{ fontSize: 11, color: 'var(--muted)' }}>{t.progress}%</span>
                      </div>
                    ) : (
                      <span style={{ fontSize: 12, color: 'var(--faint)' }}>—</span>
                    )}
                  </td>
                  <td className="num" style={{ fontSize: 12, color: 'var(--muted)' }}>{t.started}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 6 }}>
                      {(t.status === '运行中' || t.status === '等待') && (
                        <button className="btn" style={{ fontSize: 11, padding: '2px 8px' }} onClick={() => stopTask(t.id)}>终止</button>
                      )}
                      {(t.status === '完成' || t.status === '失败' || t.status === '已终止') && (
                        <button className="btn" style={{ fontSize: 11, padding: '2px 8px', color: 'var(--err)' }} onClick={() => deleteTask(t.id)}>删除</button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {visibleTasks.length === 0 && <div className="empty" style={{ padding: '16px 0', textAlign: 'center' }}>暂无训练任务</div>}
        </div>
        {visibleTasks.filter((t) => t.status === '失败' || t.status === '已终止').map((t) => (
          <div key={t.id} className="login-error" style={{ marginTop: 14 }}>
            任务 <b className="num">{t.name}</b> {t.status === '已终止' ? '已终止' : '失败'}：{t.message || '详情未知'}
          </div>
        ))}
      </div>
    </div>
  )
}
