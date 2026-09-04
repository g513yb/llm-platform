import { useOutletContext, Link } from 'react-router-dom'
import type { Domain } from '../types'
import { getBundle } from '../data/mock'
import StatusBadge from '../components/StatusBadge'
import { RadarChart } from '../components/charts'

export default function Overview() {
  const { domain } = useOutletContext<{ domain: Domain }>()
  const b = getBundle(domain.id)
  const bestEval = [...b.evals].sort((a, c) => c.composite - a.composite)[0]
  const running = b.tasks.filter((t) => t.status === '运行中' || t.status === '等待').length

  return (
    <div>
      <h1 className="page-title display">{domain.name}领域 · 工作台概览</h1>
      <p className="page-sub">
        {domain.description} 本页汇总该领域的数据资产、训练活动与模型能力，帮助你掌握当前领域工作流的整体状态。
      </p>

      <div className="grid cols-4">
        <div className="card stat-card">
          <div className="k">数据集 / 版本</div>
          <div className="v">{b.datasets.length}<span style={{ fontSize: 15, color: 'var(--faint)' }}> · {b.datasets.length + 5}版本</span></div>
          <div className="d">最新更新 {b.datasets[0].updated}</div>
        </div>
        <div className="card stat-card">
          <div className="k">训练任务（活动）</div>
          <div className="v">{running}<span style={{ fontSize: 15, color: 'var(--faint)' }}> / {b.tasks.length}</span></div>
          <div className="d">含等待与运行中任务</div>
        </div>
        <div className="card stat-card">
          <div className="k">领域模型</div>
          <div className="v">{b.models.length}</div>
          <div className="d">{b.models.filter((m) => m.status === '可用').length} 个可用权重</div>
        </div>
        <div className="card stat-card">
          <div className="k">最佳综合评分</div>
          <div className="v" style={{ color: 'var(--accent)' }}>{bestEval.composite}</div>
          <div className="d">{bestEval.model}</div>
        </div>
      </div>

      <div className="grid cols-2" style={{ marginTop: 18 }}>
        <div className="card">
          <h3>最新训练任务</h3>
          <p className="card-sub">FR-11 · 训练任务状态查看</p>
          <div className="tbl-scroll">
            <table className="tbl">
              <thead>
                <tr><th>任务</th><th>基础模型</th><th>状态</th><th>进度</th></tr>
              </thead>
              <tbody>
                {b.tasks.slice(0, 4).map((t) => (
                  <tr key={t.id}>
                    <td className="num" style={{ fontSize: 12.5 }}>{t.name}</td>
                    <td>{t.baseModel}</td>
                    <td><StatusBadge status={t.status} /></td>
                    <td>
                      {t.status === '运行中' ? (
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                          <div className="progress"><i style={{ width: `${t.progress}%` }} /></div>
                          <span className="num" style={{ fontSize: 11, color: 'var(--muted)' }}>{t.progress}%</span>
                        </div>
                      ) : (
                        <span className="num" style={{ fontSize: 11, color: 'var(--faint)' }}>—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <h3>最佳模型能力画像</h3>
          <p className="card-sub">FR-17 / FR-19 · 多维度评测与综合评分</p>
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <RadarChart labels={['专业知识', '推理能力', '表达准确', '安全合规', '领域适应', '任务完成']} series={[{ name: bestEval.model, color: 'var(--accent)', values: bestEval.dims }]} />
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 18 }}>
        <h3>下一步</h3>
        <p className="card-sub">按领域工作流推进</p>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <Link className="btn ghost sm" to={`/domain/${domain.id}/datasets`}>导入数据集（FR-03）</Link>
          <Link className="btn ghost sm" to={`/domain/${domain.id}/training`}>创建训练任务（FR-10）</Link>
          <Link className="btn ghost sm" to={`/domain/${domain.id}/chat`}>加载模型对话（FR-13）</Link>
          <Link className="btn primary sm" to={`/domain/${domain.id}/evaluation`}>配置评测任务（FR-16）</Link>
        </div>
      </div>
    </div>
  )
}
