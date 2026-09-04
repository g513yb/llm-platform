import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { useOutletContext } from 'react-router-dom'
import type { Dataset, Domain } from '../types'
import { getBundle } from '../data/mock'

const fmt = (n: number) => n.toLocaleString('zh-CN')
const API_BASE = 'http://127.0.0.1:8000'

interface ProcessResult {
  datasetId: string
  version: string
  filename: string
  stats: { input: number; output: number; filtered: number; quality: number; duplicate: number; blank: number; tooShort: number; tooLong: number; domainRisk: number }
  steps: { label: string; in: number; out: number }[]
}

export default function Datasets() {
  const { domain } = useOutletContext<{ domain: Domain }>()
  const b = getBundle(domain.id)
  const [datasets, setDatasets] = useState<Dataset[]>(b.datasets)
  const [selected, setSelected] = useState<Dataset>(b.datasets[0])
  const [importing, setImporting] = useState(false)
  const [imported, setImported] = useState(false)
  const [processResult, setProcessResult] = useState<ProcessResult | null>(null)
  const [error, setError] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const loadDatasets = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/datasets?domain=${domain.id}`)
        if (!response.ok) return
        const data = await response.json()
        const saved = data.list || data.data?.list || []
        if (saved.length > 0) {
          setDatasets(saved)
          setSelected(saved[0])
        }
      } catch {
        // Keep the local fallback data when the backend is temporarily unavailable.
      }
    }
    loadDatasets()
  }, [domain.id])

  const startImport = () => fileInput.current?.click()

  const handleFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    setImporting(true)
    setImported(false)
    setProcessResult(null)
    setError('')
    try {
      const formData = new FormData()
      formData.append('file', file)
      const uploadResponse = await fetch(`${API_BASE}/api/datasets/upload`, { method: 'POST', body: formData })
      const upload = await uploadResponse.json()
      if (!uploadResponse.ok || upload.error) throw new Error(upload.error || '上传失败')

      const processResponse = await fetch(`${API_BASE}/api/datasets/${upload.datasetId}/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ domain: domain.id, minLength: 2, maxLength: 12000 }),
      })
      const processed = await processResponse.json()
      if (!processResponse.ok || processed.error) throw new Error(processed.error || '处理失败')
      setProcessResult(processed)
      const processedDataset: Dataset = {
        id: processed.datasetId,
        name: file.name,
        version: processed.version,
        rows: processed.stats.output,
        updated: new Date().toISOString().slice(0, 10),
        quality: processed.stats.quality,
        splits: { train: 80, val: 10, test: 10 },
        steps: processed.steps.map((step: { label: string; in: number; out: number }, index: number) => ({
          ...step,
          fr: ['FR-04', 'FR-05', 'FR-05', 'FR-07', 'FR-06'][index] || 'FR-05',
        })),
      }
      setDatasets((current) => [processedDataset, ...current.filter((item) => item.id !== processedDataset.id)])
      setSelected(processedDataset)
      setImported(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : '上传或处理失败')
    } finally {
      setImporting(false)
      event.target.value = ''
    }
  }

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
        <div style={{ display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap' }}>
          <div
            style={{
              flex: 1, minWidth: 280, border: '1.5px dashed var(--line)', borderRadius: 9,
              padding: '18px 20px', textAlign: 'center', color: 'var(--muted)', fontSize: 13,
              background: 'color-mix(in srgb, var(--accent) 3%, white)',
            }}
          >
            {error ? (
              <span style={{ color: 'var(--err)', fontWeight: 600 }}>{error}</span>
            ) : imported ? (
              <span style={{ color: 'var(--ok)', fontWeight: 600 }}>
                ✓ {processResult?.filename} 已保存，清洗与标注完成
              </span>
            ) : importing ? (
              <span style={{ color: 'var(--accent)' }}>正在校验数据格式与完整性…</span>
            ) : (
              <>拖拽文件到此处，或点击下方按钮导入 <span className="num" style={{ fontSize: 11 }}>.jsonl / .csv / .txt</span></>
            )}
          </div>
          <input ref={fileInput} type="file" accept=".jsonl,.csv,.json,.txt" onChange={handleFile} style={{ display: 'none' }} />
          <button className="btn primary" onClick={startImport} disabled={importing}>
            {importing ? '处理中…' : '选择文件导入并处理'}
          </button>
        </div>
      </div>

      {processResult && (
        <div className="card">
          <h3>处理结果 · {processResult.version}</h3>
          <p className="card-sub">已保存为新的 JSONL 版本，原始文件保持不变</p>
          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', fontSize: 13 }}>
            <span>原始样本 <b className="num">{fmt(processResult.stats.input)}</b></span>
            <span>保留样本 <b className="num" style={{ color: 'var(--ok)' }}>{fmt(processResult.stats.output)}</b></span>
            <span>过滤样本 <b className="num" style={{ color: 'var(--err)' }}>{fmt(processResult.stats.filtered)}</b></span>
            <span>保留率 <b className="num" style={{ color: 'var(--accent)' }}>{processResult.stats.quality}%</b></span>
            <span>重复 <b className="num">{fmt(processResult.stats.duplicate)}</b></span>
            <span>空/过短/过长 <b className="num">{processResult.stats.blank}/{processResult.stats.tooShort}/{processResult.stats.tooLong}</b></span>
          </div>
          <a className="btn ghost sm" style={{ display: 'inline-block', marginTop: 16 }} href={`${API_BASE}/api/datasets/${processResult.datasetId}/download/${processResult.version}`} download>
            下载处理后的数据集
          </a>
        </div>
      )}

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
              {datasets.map((d) => (
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
    </div>
  )
}
