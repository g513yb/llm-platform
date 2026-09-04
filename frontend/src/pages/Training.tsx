import { useEffect, useState, type ChangeEvent } from 'react'
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
})

export default function Training() {
  const { domain } = useOutletContext<{ domain: Domain }>()
  const [tasks, setTasks] = useState<TrainTask[]>([])
  const [created, setCreated] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [dsInfo, setDsInfo] = useState<{ filename: string; samples: number } | null>(null)
  const [errMsg, setErrMsg] = useState('')

  const [form, setForm] = useState({
    name: `${domain.en}-LoRA-r16-e3`,
    datasetId: '',
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
    refreshJobs()
    const t = setInterval(refreshJobs, 2000)
    return () => clearInterval(t)
  }, [])

  const onFile = async (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    setUploading(true)
    setErrMsg('')
    try {
      const fd = new FormData()
      fd.append('file', f)
      const r = await fetch(`${API_BASE}/api/datasets/upload`, { method: 'POST', body: fd }).then((x) => x.json())
      if (r.error) {
        setErrMsg(r.error as string)
        setDsInfo(null)
        setForm((s) => ({ ...s, datasetId: '' }))
        return
      }
      setForm((s) => ({ ...s, datasetId: r.datasetId as string }))
      setDsInfo({ filename: r.filename as string, samples: r.samples as number })
    } catch {
      setErrMsg('上传失败：无法连接本地服务')
    } finally {
      setUploading(false)
    }
  }

  const create = async () => {
    if (!form.name.trim()) return
    if (!form.datasetId) { setErrMsg('请先选择并上传数据集'); return }
    setErrMsg('')
    const taskName = form.name.trim()
    const datasetLabel = dsInfo ? `${dsInfo.filename}（${dsInfo.samples} 条）` : '本地数据集'
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

  const latest = tasks[0]

  return (
    <div>
      <h1 className="page-title display">模型训练</h1>
      <p className="page-sub">
        基于固定基座模型 {BASE_MODEL}（LoRA · 4bit 量化，适配 8GB 显存），选择数据集版本并调整超参数创建训练任务。任务在后台执行（FR-09 ~ FR-12），完成后领域权重自动入库。
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
            <label>基础模型 <span className="hint">固定基座，不支持选择</span></label>
            <input value={BASE_MODEL} readOnly />
          </div>
          <div className="field">
            <label htmlFor="t-path">模型路径 <span className="hint">本地权重位置，可自行指定</span></label>
            <input id="t-path" value={form.modelPath} onChange={(e) => setForm({ ...form, modelPath: e.target.value })} />
          </div>
          <div className="field">
            <label>数据集 <span className="hint">选择本地 csv/txt/json/jsonl 文件</span></label>
            <input type="file" accept=".csv,.txt,.json,.jsonl" onChange={onFile} style={{ fontSize: 12.5 }} />
            {uploading && <span style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4, display: 'block' }}>上传中……</span>}
            {dsInfo && !uploading && (
              <span style={{ fontSize: 12, color: 'var(--ok)', marginTop: 4, display: 'block' }}>✓ {dsInfo.filename} · {dsInfo.samples} 条样本</span>
            )}
          </div>
          <div className="grid cols-2" style={{ gap: 12 }}>
            <div className="field">
              <label>微调方法 <span className="hint">固定，不支持选择</span></label>
              <input value={`${FINETUNE_METHOD} · ${QUANT_BITS} 量化`} readOnly />
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
            <button className="btn primary" onClick={create}>启动训练任务</button>
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
                {BASE_MODEL} <span className="badge" style={{ marginLeft: 6 }}>LoRA·4bit</span>
              </div>
            </div>
          </div>
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
              {tasks.map((t) => (
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
          {tasks.length === 0 && <div className="empty" style={{ padding: '16px 0', textAlign: 'center' }}>暂无训练任务</div>}
        </div>
        {tasks.filter((t) => t.status === '失败' || t.status === '已终止').map((t) => (
          <div key={t.id} className="login-error" style={{ marginTop: 14 }}>
            任务 <b className="num">{t.name}</b> {t.status === '已终止' ? '已终止' : '失败'}：{t.message || '详情未知'}
          </div>
        ))}
      </div>
    </div>
  )
}
