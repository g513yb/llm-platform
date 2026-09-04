export type DomainId = 'medical' | 'legal' | 'finance' | 'education'

export interface Domain {
  id: DomainId
  name: string
  en: string
  accent: string
  tagline: string
  description: string
}

export type TaskStatus = '等待' | '运行中' | '完成' | '失败' | '已终止'

export interface ProcessStep {
  label: string
  fr: string
  in: number
  out: number
}

export interface Dataset {
  id: string
  name: string
  version: string
  rows: number
  updated: string
  quality: number
  splits: { train: number; val: number; test: number }
  steps: ProcessStep[]
}

export interface TrainTask {
  id: string
  name: string
  baseModel: string
  dataset: string
  status: TaskStatus
  progress: number
  loss: number
  evalLoss: number
  started: string
  curve: number[]
  message?: string
}

export interface DomainModel {
  id: string
  name: string
  baseModel: string
  trainedOn: string
  sizeGB: number
  status: '可用' | '训练中' | '归档'
}

export const EVAL_DIMS = ['专业知识', '推理能力', '表达准确', '安全合规', '领域适应', '任务完成'] as const
export type EvalDim = (typeof EVAL_DIMS)[number]

export interface EvalTask {
  id: string
  model: string
  testSet: string
  status: TaskStatus
  composite: number
  dims: number[]
  finished: string
}

export interface ChatMsg {
  role: 'user' | 'assistant'
  content: string
  time: string
}

export interface ChatSession {
  id: string
  title: string
  model: string
  messages: ChatMsg[]
}

export interface DomainBundle {
  datasets: Dataset[]
  tasks: TrainTask[]
  models: DomainModel[]
  evals: EvalTask[]
  sessions: ChatSession[]
  replySeeds: string[]
}
