import type { Domain, DomainBundle, DomainId } from '../types'

export const DOMAINS: Domain[] = [
  {
    id: 'medical',
    name: '医疗',
    en: 'MEDICAL',
    accent: '#0B8A6D',
    tagline: '临床诊疗 · 医学知识 · 病历理解',
    description: '面向临床问答、医学文献理解与病历结构化的领域模型训练与评测。',
  },
  {
    id: 'legal',
    name: '法律',
    en: 'LEGAL',
    accent: '#5A4BD8',
    tagline: '法条检索 · 案例分析 · 合同审查',
    description: '面向法条适用、类案检索与法律文书生成的领域模型训练与评测。',
  },
  {
    id: 'finance',
    name: '金融',
    en: 'FINANCE',
    accent: '#C07A0A',
    tagline: '研报解读 · 风险识别 · 合规问答',
    description: '面向金融研报理解、风险事件识别与投资问答的领域模型训练与评测。',
  },
  {
    id: 'education',
    name: '教育',
    en: 'EDUCATION',
    accent: '#D14D3F',
    tagline: '学科辅导 · 习题讲解 · 学情诊断',
    description: '面向 K12 与高教学科辅导、习题讲解与个性化反馈的领域模型训练与评测。',
  },
]

export const getDomain = (id: string | undefined): Domain =>
  DOMAINS.find((d) => d.id === id) ?? DOMAINS[0]

/* ---------------- 每个领域的确定性模拟数据 ---------------- */

function bundle(domain: Domain): DomainBundle {
  const d = domain.id
  const seed = { medical: 0.82, legal: 0.76, finance: 0.79, education: 0.74 }[d]
  const dims = [
    seed + 0.10, seed - 0.02, seed + 0.05, seed + 0.08, seed - 0.04, seed + 0.02,
  ].map((v) => Math.round(Math.min(v, 0.95) * 100))

  const raw = [128400, 96200, 84300, 112600][DOMAINS.indexOf(domain)]
  const steps = [
    { label: '格式检查', fr: 'FR-04', in: raw, out: raw - 2100 },
    { label: '数据清洗', fr: 'FR-05', in: raw - 2100, out: raw - 5600 },
    { label: '去重', fr: 'FR-05', in: raw - 5600, out: raw - 8300 },
    { label: '质量过滤', fr: 'FR-07', in: raw - 8300, out: raw - 10800 },
    { label: '标注格式化', fr: 'FR-06', in: raw - 10800, out: raw - 11400 },
  ]

  return {
    datasets: [
      {
        id: `${d}-ds-1`,
        name: `${domain.name}领域指令语料库`,
        version: 'v2.1.0',
        rows: raw - 11400,
        updated: '2026-08-27',
        quality: 96,
        splits: { train: 82, val: 10, test: 8 },
        steps,
      },
      {
        id: `${d}-ds-2`,
        name: `${domain.name}多轮对话数据集`,
        version: 'v1.4.0',
        rows: Math.round((raw - 11400) * 0.36),
        updated: '2026-08-14',
        quality: 91,
        splits: { train: 80, val: 12, test: 8 },
        steps,
      },
      {
        id: `${d}-ds-3`,
        name: `${domain.name}领域基准测试集`,
        version: 'v1.0.2',
        rows: 4800,
        updated: '2026-07-30',
        quality: 99,
        splits: { train: 0, val: 20, test: 80 },
        steps,
      },
    ],
    tasks: [
      {
        id: `${d}-tk-1`,
        name: `${domain.en}-LoRA-r16-e3`,
        baseModel: 'Qwen2.5-3B-Instruct',
        dataset: `${domain.name}领域指令语料库 v2.1.0`,
        status: '完成',
        progress: 100,
        loss: 0.68,
        evalLoss: 0.74,
        started: '2026-08-28 09:12',
        curve: [2.31, 1.85, 1.52, 1.28, 1.11, 0.98, 0.89, 0.82, 0.76, 0.71, 0.68],
      },
      {
        id: `${d}-tk-2`,
        name: `${domain.en}-LoRA-r32-e2`,
        baseModel: 'Qwen2.5-3B-Instruct',
        dataset: `${domain.name}多轮对话数据集 v1.4.0`,
        status: '运行中',
        progress: 64,
        loss: 0.91,
        evalLoss: 0.95,
        started: '2026-09-01 07:40',
        curve: [2.18, 1.72, 1.41, 1.19, 1.02, 0.91],
      },
      {
        id: `${d}-tk-3`,
        name: `${domain.en}-LoRA-r64-e1`,
        baseModel: 'Qwen2.5-3B-Instruct',
        dataset: `${domain.name}领域指令语料库 v2.0.0`,
        status: '失败',
        progress: 43,
        loss: 1.24,
        evalLoss: 1.31,
        started: '2026-08-21 14:05',
        curve: [2.42, 1.98, 1.61, 1.44, 1.31, 1.24],
      },
      {
        id: `${d}-tk-4`,
        name: `${domain.en}-LoRA-r8-e3`,
        baseModel: 'Qwen2.5-3B-Instruct',
        dataset: `${domain.name}领域指令语料库 v1.9.0`,
        status: '等待',
        progress: 0,
        loss: 0,
        evalLoss: 0,
        started: '—',
        curve: [],
      },
    ],
    models: [
      {
        id: `${d}-m-1`,
        name: `${domain.en}-Qwen2.5-3B-v2.1`,
        baseModel: 'Qwen2.5-3B-Instruct',
        trainedOn: '语料库 v2.1.0',
        sizeGB: 2.1,
        status: '可用',
      },
      {
        id: `${d}-m-2`,
        name: `${domain.en}-Qwen2.5-3B-v1.4`,
        baseModel: 'Qwen2.5-3B-Instruct',
        trainedOn: '对话集 v1.4.0',
        sizeGB: 1.9,
        status: '可用',
      },
      {
        id: `${d}-m-3`,
        name: `${domain.en}-Qwen2.5-3B-v0.9`,
        baseModel: 'Qwen2.5-3B-Instruct',
        trainedOn: '语料库 v2.0.0',
        sizeGB: 1.7,
        status: '归档',
      },
    ],
    evals: [
      {
        id: `${d}-ev-1`,
        model: `${domain.en}-Qwen2.5-3B-v2.1`,
        testSet: '基准测试集 v1.0.2',
        status: '完成',
        composite: Math.round(dims.reduce((a, b) => a + b, 0) / dims.length),
        dims,
        finished: '2026-08-30 16:22',
      },
      {
        id: `${d}-ev-2`,
        model: `${domain.en}-Qwen2.5-3B-v1.4`,
        testSet: '基准测试集 v1.0.2',
        status: '完成',
        composite: Math.round(dims.reduce((a, b) => a + b, 0) / dims.length) - 3,
        dims: dims.map((v) => Math.max(40, v - 4)),
        finished: '2026-08-26 11:08',
      },
      {
        id: `${d}-ev-3`,
        model: `${domain.en}-Qwen2.5-3B-v0.9`,
        testSet: '基准测试集 v0.9.7',
        status: '完成',
        composite: Math.round(dims.reduce((a, b) => a + b, 0) / dims.length) - 6,
        dims: dims.map((v) => Math.max(38, v - 7)),
        finished: '2026-08-18 19:45',
      },
    ],
    sessions: [
      {
        id: `${d}-s-1`,
        title: `${domain.tagline.split(' · ')[0]}能力验证`,
        model: `${domain.en}-Qwen2.5-3B-v2.1`,
        messages: [],
      },
    ],
    replySeeds: [
      `基于${domain.name}领域知识的分析：综合训练语料中的相关依据，该问题应从以下几个方面理解——首先，需要明确问题在${domain.name}场景下的规范定义；其次，参考领域内权威来源给出的通行做法；最后，结合具体情境给出有依据的结论。以上分析仅供参考，重要决策请咨询${domain.name}领域专业人员。`,
      `这是一个很好的${domain.name}领域问题。根据微调数据中的典型案例，可以归纳出三类常见情形，分别对应不同的处理路径。若您能补充更多上下文，我可以给出更有针对性的回答。`,
      `从${domain.name}领域的角度，这个问题涉及知识检索与推理两个环节。当前模型在这两个维度上的评测得分分别为 ${dims[0]} 与 ${dims[1]} 分，相关结论的可信度较高，但仍建议交叉验证关键事实。`,
    ],
  }
}

const bundles: Record<DomainId, DomainBundle> = {
  medical: bundle(DOMAINS[0]),
  legal: bundle(DOMAINS[1]),
  finance: bundle(DOMAINS[2]),
  education: bundle(DOMAINS[3]),
}

export const getBundle = (id: DomainId): DomainBundle => bundles[id]

export const BASE_MODEL = 'Qwen2.5-3B-Instruct'
export const MODEL_PATH = 'C:\\Qwen2.5-3B-Instruct'
export const FINETUNE_METHOD = 'LoRA'
export const QUANT_BITS = '4bit'

export const now = () =>
  new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
