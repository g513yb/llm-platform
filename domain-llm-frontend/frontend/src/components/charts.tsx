/* 手写 SVG 图表：雷达图 / 折线图 / 评分环 */

export function RadarChart({
  labels,
  series,
  size = 260,
}: {
  labels: readonly string[]
  series: { name: string; color: string; values: number[] }[]
  size?: number
}) {
  const cx = size / 2
  const cy = size / 2
  const r = size / 2 - 34
  const n = labels.length
  const pt = (i: number, v: number) => {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2
    return [cx + Math.cos(a) * r * v, cy + Math.sin(a) * r * v]
  }
  const rings = [0.25, 0.5, 0.75, 1]

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="能力雷达图">
      {rings.map((rv) => (
        <polygon
          key={rv}
          points={labels.map((_, i) => pt(i, rv).join(',')).join(' ')}
          fill="none"
          stroke="#d9e1e9"
          strokeWidth="1"
        />
      ))}
      {labels.map((_, i) => {
        const [x, y] = pt(i, 1)
        return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="#d9e1e9" strokeWidth="1" />
      })}
      {series.map((s) => (
        <g key={s.name}>
          <polygon
            points={s.values.map((v, i) => pt(i, v / 100).join(',')).join(' ')}
            fill={s.color}
            fillOpacity="0.12"
            stroke={s.color}
            strokeWidth="2"
            strokeLinejoin="round"
          />
          {s.values.map((v, i) => {
            const [x, y] = pt(i, v / 100)
            return <circle key={i} cx={x} cy={y} r="3" fill={s.color} />
          })}
        </g>
      ))}
      {labels.map((l, i) => {
        const [x, y] = pt(i, 1.16)
        return (
          <text
            key={l}
            x={x}
            y={y}
            textAnchor={Math.abs(x - cx) < 10 ? 'middle' : x > cx ? 'start' : 'end'}
            dominantBaseline="middle"
            fontSize="11.5"
            fill="#5e6e80"
          >
            {l}
          </text>
        )
      })}
    </svg>
  )
}

export function LossCurve({ points, color }: { points: number[]; color: string }) {
  const w = 560
  const h = 200
  const pad = { l: 38, r: 12, t: 12, b: 26 }
  if (points.length < 2) return null
  const max = Math.max(...points)
  const min = Math.min(...points)
  const xs = (i: number) => pad.l + ((w - pad.l - pad.r) * i) / (points.length - 1)
  const ys = (v: number) => pad.t + (h - pad.t - pad.b) * (1 - (v - min) / (max - min || 1))
  const path = points.map((v, i) => `${i === 0 ? 'M' : 'L'}${xs(i)},${ys(v)}`).join(' ')

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} role="img" aria-label="训练损失曲线">
      {[0, 0.5, 1].map((t) => {
        const y = pad.t + (h - pad.t - pad.b) * t
        const val = max - (max - min) * t
        return (
          <g key={t}>
            <line x1={pad.l} y1={y} x2={w - pad.r} y2={y} stroke="#e6ecf2" strokeWidth="1" />
            <text x={pad.l - 6} y={y + 3} textAnchor="end" fontSize="10" fill="#8a99aa" fontFamily="monospace">
              {val.toFixed(1)}
            </text>
          </g>
        )
      })}
      {points.map((_, i) => (
        <text key={i} x={xs(i)} y={h - 8} textAnchor="middle" fontSize="9.5" fill="#8a99aa" fontFamily="monospace">
          {i + 1}
        </text>
      ))}
      <path d={path} fill="none" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      {points.map((v, i) => (
        <circle key={i} cx={xs(i)} cy={ys(v)} r="3" fill="#fff" stroke={color} strokeWidth="1.6" />
      ))}
    </svg>
  )
}

export function ScoreRing({ score, size = 148 }: { score: number; size?: number }) {
  const stroke = 10
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  return (
    <div className="score-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e3e9ef" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--accent)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${(score / 100) * c} ${c}`}
          style={{ transition: 'stroke-dasharray .8s ease' }}
        />
      </svg>
      <div className="val">
        <div style={{ textAlign: 'center' }}>
          <b>{score}</b>
          <span>COMPOSITE</span>
        </div>
      </div>
    </div>
  )
}
