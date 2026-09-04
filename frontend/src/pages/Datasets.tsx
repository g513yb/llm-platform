import { useRef, useState, type ChangeEvent } from 'react'
import { useOutletContext } from 'react-router-dom'
import type { Domain } from '../types'
import { getBundle } from '../data/mock'

const API_BASE = import.meta.env.VITE_API_BASE || ''

interface InspectResult {
  datasetId: string
  filename: string
  kept: number
  dropped: number
  typeCounts: Record<string, number>
}

interface ProcessResult {
  total: number
  kept: number
  dropped: number
  outputFiles: string[]
  preview: { instruction: string; input: string; output: string }[]
}

type Phase = 'idle' | 'inspecting' | 'inspected' | 'processing' | 'done'

const fmt = (n: number) => n.toLocaleString('zh-CN')

export default function Datasets() {
  const { domain } = useOutletContext<{ domain: Domain }>()
  const b = getBundle(domain.id)
  const [selected, setSelected] = useState(b.datasets[0])
  const [phase, setPhase] = useState<Phase>('idle')
  const [inspectRes, setInspectRes] = useState<InspectResult | null>(null)
  const [processRes, setProcessRes] = useState<ProcessResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [fileViewer, setFileViewer] = useState<{ filename: string; content: string } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const onFile = async (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    setPhase('inspecting')
    setError(null)
    setInspectRes(null)
    setProcessRes(null)
    try {
      const fd = new FormData()
      fd.append('file', f)
      fd.append('domain', domain.name)
      const r = await fetch(`${API_BASE}/api/datasets/upload`, { method: 'POST', body: fd }).then((x) => x.json())
      if (r.error) {
        setError(r.error)
        setPhase('idle')
      } else {
        setInspectRes(r)
        setPhase('inspected')
      }
    } catch (err) {
      setError(String(err))
      setPhase('idle')
    } finally {
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const onProcess = async () => {
    if (!inspectRes) return
    setPhase('processing')
    setError(null)
    try {
      const r = await fetch(`${API_BASE}/api/datasets/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ datasetId: inspectRes.datasetId, domain: domain.name }),
      }).then((x) => x.json())
      if (r.error) {
        setError(r.error)
        setPhase('inspected')
      } else {
        setProcessRes(r)
        setPhase('done')
      }
    } catch (err) {
      setError(String(err))
      setPhase('inspected')
    }
  }

  const onViewFile = async (filename: string) => {
    setError(null)
    try {
      const r = await fetch(`${API_BASE}/api/datasets/output/${encodeURIComponent(filename)}`).then((x) => x.json())
      if (r.error) {
        setError(r.error)
      } else {
        setFileViewer({ filename: r.filename, content: r.content })
      }
    } catch (err) {
      setError(String(err))
    }
  }

  const busy = phase === 'inspecting' || phase === 'processing'

  return (
    <div>
      <h1 className="page-title display">数据集管理</h1>
      <p className="page-sub">
        导入领域语料，执行格式检查、清洗、去重、质量过滤与标注格式化，并以版本形式沉淀，供训练任务精确引用。
      </p>

      {/* 导入 */}
      <div className="card">
        <h3>导入数据集</h3>
        <p className="card-sub">FR-03 · 数据集导入 ／ FR-04 · 格式检查</p>
        <input ref={fileRef} type="file" accept=".csv,.txt,.json,.jsonl" hidden onChange={onFile} />
        <div style={{ display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap' }}>
          <div
            style={{
              flex: 1, minWidth: 280, border: '1.5px dashed var(--line)', borderRadius: 9,
              padding: '18px 20px', textAlign: 'center', color: 'var(--muted)', fontSize: 13,
              background: 'color-mix(in srgb, var(--accent) 3%, white)',
            }}
          >
            {phase === 'inspecting' ? (
              <span style={{ color: 'var(--accent)' }}>正在识别数据格式…</span>
            ) : phase === 'inspected' && inspectRes ? (
              <div style={{ textAlign: 'left' }}>
                <span style={{ color: 'var(--ok)', fontWeight: 600 }}>✓ {inspectRes.filename} 识别通过</span>
                <div style={{ marginTop: 6, fontSize: 12, color: 'var(--muted)' }}>
                  可用 {fmt(inspectRes.kept)} · 丢弃 {fmt(inspectRes.dropped)}
                  {Object.keys(inspectRes.typeCounts).length > 0 && (
                    <> · 类型 {Object.entries(inspectRes.typeCounts).map(([k, v]) => `${k}:${v}`).join('、')}</>
                  )}
                </div>
              </div>
            ) : phase === 'processing' ? (
              <span style={{ color: 'var(--accent)' }}>正在处理并生成输出文件…</span>
            ) : phase === 'done' && processRes ? (
              <div style={{ textAlign: 'left' }}>
                <span style={{ color: 'var(--ok)', fontWeight: 600 }}>✓ 处理完成</span>
                <div style={{ marginTop: 6, fontSize: 12, color: 'var(--muted)' }}>
                  总数 {fmt(processRes.total)} · 保留 {fmt(processRes.kept)} · 丢弃 {fmt(processRes.dropped)}
                </div>
                {processRes.outputFiles.map((f) => (
                  <a
                    key={f}
                    onClick={() => onViewFile(f)}
                    style={{ cursor: 'pointer', fontSize: 12, color: 'var(--accent)', marginTop: 4, display: 'block', wordBreak: 'break-all', textDecoration: 'underline' }}
                  >
                    📄 {f}
                  </a>
                ))}
              </div>
            ) : error ? (
              <span style={{ color: 'var(--err)' }}>✗ {error}</span>
            ) : (
              <>拖拽文件到此处，或点击下方按钮导入 <span className="num" style={{ fontSize: 11 }}>.jsonl / .csv / .txt</span></>
            )}
          </div>
          <button className="btn primary" onClick={() => fileRef.current?.click()} disabled={busy}>
            {phase === 'inspecting' ? '识别中…' : '选择文件导入'}
          </button>
          {(phase === 'inspected' || phase === 'processing') && (
            <button className="btn primary" onClick={onProcess} disabled={busy}>
              {phase === 'processing' ? '处理中…' : '处理'}
            </button>
          )}
        </div>
        {phase === 'done' && processRes && processRes.preview.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h4 style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 8 }}>
              预览（前 {Math.min(5, processRes.preview.length)} 条 · Alpaca 格式）
            </h4>
            <div className="tbl-scroll">
              <table className="tbl">
                <thead><tr><th>instruction</th><th>input</th><th>output</th></tr></thead>
                <tbody>
                  {processRes.preview.slice(0, 5).map((p, i) => (
                    <tr key={i}>
                      <td style={{ maxWidth: 350 }}>{p.instruction}</td>
                      <td style={{ maxWidth: 200 }}>{p.input || '—'}</td>
                      <td style={{ maxWidth: 350 }}>{p.output}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* 数据集列表 */}
      <div className="card">
        <h3>领域数据集</h3>
        <p className="card-sub">FR-08 · 数据集版本管理</p>
        <div className="tbl-scroll">
          <table className="tbl">
            <thead>
              <tr><th>数据集</th><th>版本</th><th>样本数</th><th>质量分</th><th>数据划分</th><th>更新时间</th><th /></tr>
            </thead>
            <tbody>
              {b.datasets.map((d) => (
                <tr key={d.id} style={{ cursor: 'pointer', background: selected.id === d.id ? 'color-mix(in srgb, var(--accent) 5%, white)' : undefined }} onClick={() => setSelected(d)}>
                  <td style={{ fontWeight: 600 }}>{d.name}</td>
                  <td><span className="badge num" style={{ fontSize: 11 }}>{d.version}</span></td>
                  <td className="num">{fmt(d.rows)}</td>
                  <td className="num" style={{ color: d.quality >= 95 ? 'var(--ok)' : 'var(--warn)' }}>{d.quality}</td>
                  <td className="num" style={{ fontSize: 12, color: 'var(--muted)' }}>
                    训练 {d.splits.train}% · 验证 {d.splits.val}% · 测试 {d.splits.test}%
                  </td>
                  <td className="num" style={{ fontSize: 12, color: 'var(--muted)' }}>{d.updated}</td>
                  <td>
                    <button className="btn ghost sm">创建训练任务</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 数据处理流水线（选中数据集） */}
      <div className="card">
        <h3>数据处理统计 · {selected.name} <span className="num" style={{ fontSize: 12, color: 'var(--faint)' }}>{selected.version}</span></h3>
        <p className="card-sub">FR-05 / FR-06 / FR-07 / FR-21 · 清洗 → 去重 → 质量过滤 → 标注格式化，记录各环节数据量变化</p>
        <div className="funnel">
          <div className="funnel-node src">
            <div className="cnt">{fmt(selected.steps[0].in)}</div>
            <div className="lb">原始数据</div>
            <div className="fr">RAW</div>
          </div>
          {selected.steps.map((s) => (
            <div className="funnel-node" key={s.label}>
              <div className="cnt">{fmt(s.out)}</div>
              <div className="lb">{s.label}</div>
              <div className="fr">{s.fr}</div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 14, fontSize: 12.5, color: 'var(--muted)' }}>
          共处理 <b className="num">{fmt(selected.steps[0].in)}</b> 条原始数据，过滤无效样本
          <b className="num" style={{ color: 'var(--err)' }}> {fmt(selected.steps[0].in - selected.steps[selected.steps.length - 1].out)} </b>
          条（空数据、重复、异常与低质量），保留率
          <b className="num" style={{ color: 'var(--accent)' }}>
            {' '}{((selected.steps[selected.steps.length - 1].out / selected.steps[0].in) * 100).toFixed(1)}%
          </b>。
          处理结果已随版本 <span className="num">{selected.version}</span> 固化，可追溯。
        </div>
      </div>

      {fileViewer && (
        <div
          onClick={() => setFileViewer(null)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{ background: 'white', borderRadius: 10, padding: 24, maxWidth: '80vw', maxHeight: '80vh', overflow: 'auto', boxShadow: '0 8px 32px rgba(0,0,0,0.2)' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ margin: 0, fontSize: 15 }}>{fileViewer.filename}</h3>
              <button className="btn ghost sm" onClick={() => setFileViewer(null)}>关闭</button>
            </div>
            <pre style={{ fontSize: 12, whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: '60vh', overflow: 'auto', margin: 0 }}>
              {fileViewer.content}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}
