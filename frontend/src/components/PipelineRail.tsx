import { useNavigate, useLocation } from 'react-router-dom'

const STAGES = [
  { key: 'datasets', label: '数据', fr: 'FR-03~08' },
  { key: 'training', label: '训练', fr: 'FR-09~12' },
  { key: 'chat', label: '对话', fr: 'FR-13~15' },
  { key: 'evaluation', label: '评测', fr: 'FR-16~20' },
]

export default function PipelineRail({ domainId, title }: { domainId: string; title: string }) {
  const nav = useNavigate()
  const { pathname } = useLocation()
  const current = pathname.split('/').pop() ?? ''
  const activeIdx = STAGES.findIndex((s) => s.key === current)

  return (
    <div className="rail-wrap">
      <div>
        <div className="rail-title">
          <span className="eyebrow">{title}</span>
        </div>
        <div className="rail-meta" style={{ marginTop: 4 }}>
          领域工作流 · DOMAIN PIPELINE
        </div>
      </div>
      <nav className="rail" aria-label="领域工作流">
        {STAGES.map((s, i) => {
          const state = i === activeIdx ? 'active' : i < activeIdx ? 'done' : 'todo'
          return (
            <span key={s.key} style={{ display: 'contents' }}>
              {i > 0 && <span className={`rail-link ${activeIdx >= i ? 'lit' : ''}`} />}
              <button
                type="button"
                className={`rail-step ${state}`}
                onClick={() => nav(`/domain/${domainId}/${s.key}`)}
                title={`${s.fr}`}
              >
                <span className="stage">{i + 1}</span>
                {s.label}
              </button>
            </span>
          )
        })}
      </nav>
    </div>
  )
}
