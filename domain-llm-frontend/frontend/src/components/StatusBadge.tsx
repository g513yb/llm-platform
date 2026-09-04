import type { TaskStatus } from '../types'

const CLASS_MAP: Record<TaskStatus, string> = {
  '等待': 's-等待',
  '运行中': 's-运行中',
  '完成': 's-完成',
  '失败': 's-失败',
  '已终止': 's-失败',
}

export default function StatusBadge({ status }: { status: TaskStatus }) {
  return <span className={`badge ${CLASS_MAP[status]}`}>{status}</span>
}
