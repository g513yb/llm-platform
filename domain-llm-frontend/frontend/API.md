# 领域大模型训练与评测平台 · 前端交付说明与接口契约

> 版本：v1.0 ｜ 日期：2026-09-02
> 前端技术栈：Vite 5 + React 18 + TypeScript 5 + React Router 6（无 UI 组件库、无图表库，图表为手写 SVG）
> 本文档是前后端对接的唯一契约：所有接口的路径、参数、响应结构均与前端页面一一对应，后端按此实现即可直接联调。

---

## 一、交付物与运行方式

| 内容 | 说明 |
|---|---|
| `src/` | 前端全部源码（页面 / 组件 / 类型 / 模拟数据） |
| `package.json` | 依赖清单，`npm install` 后即可开发 |
| `vite.config.ts` / `tsconfig.json` / `index.html` | 构建 配置 |
| `API.md` | 本文档 |

本地开发：

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # 产物输出至 dist/
```

生产部署：托管 `dist/` 静态文件即可。前端使用 BrowserRouter，**所有未命中静态资源的路径必须 fallback 到 `index.html`**（Nginx 示例）：

```nginx
location / {
  root /path/to/dist;
  try_files $uri $uri/ /index.html;
}
```

---

## 二、通用约定

### 2.1 Base URL 与前缀

- 所有接口前缀：`/api/v1`
- 前端开发期可通过 Vite 代理转发（见文末「联调配置」）

### 2.2 鉴权

- 除 `POST /auth/login` 外，所有接口要求请求头携带 `Authorization: Bearer <token>`
- token 由登录接口下发，建议有效期 ≥ 12h（前端会话级存储，刷新页面不丢失）
- 权限不足返回 `403`，token 失效返回 `401`（前端收到 401 后自动跳转登录页）

### 2.3 统一响应格式

```jsonc
// 成功
{ "code": 0, "message": "ok", "data": { } }

// 失败
{ "code": 40001, "message": "数据集文件格式不合法：第 3 行缺少 instructions 字段", "data": null }
```

- `code = 0` 表示成功；非 0 为业务错误码，由后端自定义分段（建议：40xxx 参数/格式，41xxx 资源不存在，42xxx 权限，50xxx 服务端内部错误）
- `message` 面向用户展示，**必须说清哪里错了、怎么改**（前端直接渲染该字段），不要返回堆栈或内部代号

### 2.4 分页约定

列表接口统一支持 `?page=1&pageSize=20`，响应 `data` 结构：

```json
{ "list": [ ], "total": 128, "page": 1, "pageSize": 20 }
```

### 2.5 枚举值（前后端必须一致）

| 枚举 | 取值 |
|---|---|
| 任务状态 `status` | `等待` `运行中` `完成` `失败` |
| 模型状态 `status` | `可用` `训练中` `归档` |
| 用户角色 `role` | `user` `admin` |
| 评测维度（固定 6 项，顺序即返回顺序） | `专业知识` `推理能力` `表达准确` `安全合规` `领域适应` `任务完成` |

---

## 三、接口清单

### 3.1 认证模块

#### POST /api/v1/auth/login · 登录

对应页面：登录页。

请求：

```json
{ "username": "user", "password": "user" }
```

响应 `data`：

```json
{
  "token": "eyJhbGciOi...",
  "user": { "name": "user", "role": "user" }
}
```

说明：用户名 `admin` 登录后 `role` 必须返回 `admin`，否则「系统管理」入口不展示。

#### POST /api/v1/auth/logout · 退出

请求头携带 token，服务端使该 token 失效。响应 `data` 为 `null`。

---

### 3.2 领域模块

#### GET /api/v1/domains · 领域列表（含统计）

对应页面：领域选择页（首页）。

响应 `data`：

```json
{
  "list": [
    {
      "id": "medical",
      "name": "医疗",
      "en": "MEDICAL",
      "accent": "#0B8A6D",
      "tagline": "临床诊疗 · 医学知识 · 病历理解",
      "description": "面向临床问答、医学文献理解与病历结构化的领域模型训练与评测。",
      "stats": { "datasets": 3, "models": 3, "tasks": 4, "bestScore": 84 }
    }
  ]
}
```

字段说明：`accent` 为该领域的主题色，前端据此对整个工作空间染色，需返回十六进制色值。`stats` 用于领域卡片展示。**新增领域无需改前端**，本接口返回即渲染（对应非功能需求 2.2.6）。

---

### 3.3 数据集模块

#### GET /api/v1/domains/{domainId}/datasets · 数据集列表

对应页面：数据集管理页表格。

响应 `data.list[]`：

```json
{
  "id": "medical-ds-1",
  "name": "医疗领域指令语料库",
  "version": "v2.1.0",
  "rows": 117000,
  "updated": "2026-08-27",
  "quality": 96,
  "splits": { "train": 82, "val": 10, "test": 8 }
}
```

`splits` 为百分比，三项之和应为 100。

#### POST /api/v1/domains/{domainId}/datasets · 导入数据集

对应页面：导入区（FR-03 / FR-04）。

请求：`multipart/form-data`

| 字段 | 类型 | 说明 |
|---|---|---|
| `file` | File | `.jsonl` / `.csv` / `.txt` |

响应 `data`（格式检查结果）：

```json
{
  "datasetId": "medical-ds-4",
  "formatOk": true,
  "invalidRows": 2100,
  "totalRows": 128400,
  "errors": [
    { "line": 3, "reason": "缺少 instructions 字段" }
  ]
}
```

后端必须做格式与完整性校验（FR-04）；校验失败时 `code` 返回非 0，`message` 说明具体哪一行什么问题。

#### POST /api/datasets/{datasetId}/process · 清洗、标注并保存新版本

请求：

```json
{ "domain": "medical", "minLength": 2, "maxLength": 12000 }
```

后端会保留原始文件，并生成新的 `JSONL` 版本。每条处理后的记录严格使用 `instruction`、`input`、`output` 三个字段，适合指令微调；清理首尾空白、过滤空/过短/过长样本、去重，并按所选领域执行风险过滤。处理统计保存在版本元数据中，处理结果会保存到服务器数据集目录，不覆盖原始文件。

系统也会自动整理常见的通用数据格式，例如 `question/answer`、`prompt/completion`、`问题/回答`、`query/response`，分别转换为通用指令、`input` 问题和 `output` 答案；医疗数据集的 `department/title/ask/answer` 会转换为对应科室医生指令。

响应包含 `datasetId`、`version`、`filename`、`stats` 和各处理步骤统计。版本可通过 `GET /api/datasets/{datasetId}/versions` 查询，并通过 `GET /api/datasets/{datasetId}/download/{version}` 下载。

#### GET /api/v1/datasets/{datasetId}/pipeline · 处理流水线统计

对应页面：数据处理统计漏斗（FR-05 ~ FR-07 / FR-21）。

响应 `data`：

```json
{
  "steps": [
    { "label": "格式检查",   "fr": "FR-04", "in": 128400, "out": 126300 },
    { "label": "数据清洗",   "fr": "FR-05", "in": 126300, "out": 122800 },
    { "label": "去重",       "fr": "FR-05", "in": 122800, "out": 120100 },
    { "label": "质量过滤",   "fr": "FR-07", "in": 120100, "out": 117600 },
    { "label": "标注格式化", "fr": "FR-06", "in": 117600, "out": 117000 }
  ],
  "finalVersion": "v2.1.0"
}
```

`in/out` 为该环节进入/保留的样本数。后端需异步执行清洗，建议提供任务状态接口供轮询（见 3.4 的轮询约定）。

#### GET /api/v1/datasets/{datasetId}/versions · 版本列表（FR-08）

响应 `data.list[]`：

```json
[
  { "version": "v2.1.0", "rows": 117000, "createdAt": "2026-08-27 10:12", "note": "质量过滤规则升级" }
]
```

---

### 3.4 训练模块

#### POST /api/v1/domains/{domainId}/training/tasks · 创建微调任务

对应页面：创建微调任务表单（FR-09 / FR-10）。

请求：

```json
{
  "name": "MEDICAL-LoRA-r16-e3",
  "baseModel": "Qwen2.5-3B-Instruct",
  "datasetId": "medical-ds-1",
  "datasetVersion": "v2.1.0",
  "method": "LoRA",
  "quantBits": 4,
  "rank": 16,
  "lr": "2e-4",
  "epochs": 3,
  "batchSize": 8
}
```

响应 `data`：`{ "taskId": "medical-tk-5" }`

约束说明（前端已固定，用户不可选择）：`baseModel` 恒为 `Qwen2.5-3B-Instruct`（权重本地路径 `C:\Qwen2.5-3B-Instruct`）；`method` 恒为 `LoRA` 并采用 `4bit` 量化（QLoRA），以适配 8GB 显存。用户仅可调整 `rank`、`lr`、`epochs`、`batchSize` 等超参数。

校验规则：任务名必填；`datasetId` 与 `datasetVersion` 必须真实存在（训练任务与数据集版本一一对应，保证可追溯）。

#### GET /api/v1/domains/{domainId}/training/tasks · 任务列表

对应页面：训练任务列表（FR-11）。支持分页。

响应 `data.list[]`：

```json
{
  "id": "medical-tk-2",
  "name": "MEDICAL-LoRA-r32-e2",
  "baseModel": "Qwen2.5-3B-Instruct",
  "dataset": "医疗多轮对话数据集 v1.4.0",
  "status": "运行中",
  "progress": 64,
  "loss": 0.91,
  "evalLoss": 0.95,
  "started": "2026-09-01 07:40",
  "errorMessage": null
}
```

前端每 5s 轮询本接口刷新进度。失败任务必须在 `errorMessage` 中给出可读的原因与建议（前端原样展示），例如：`"训练过程梯度不稳定（loss 发散）。建议降低学习率后重新提交。"`

#### GET /api/v1/training/tasks/{taskId}/curve · 损失曲线

对应页面：训练结果卡片（FR-22）。

响应 `data`：

```json
{ "points": [2.31, 1.85, 1.52, 1.28, 1.11, 0.98, 0.89, 0.82, 0.76, 0.71, 0.68] }
```

`points[i]` 为第 `i+1` 个 checkpoint 的训练 loss。

#### GET /api/v1/domains/{domainId}/models · 领域模型列表

对应页面：模型选择下拉框（FR-12 / FR-13）。

响应 `data.list[]`：

```json
{
  "id": "medical-m-1",
  "name": "MEDICAL-Qwen2.5-3B-v2.1",
  "baseModel": "Qwen2.5-3B-Instruct",
  "trainedOn": "语料库 v2.1.0",
  "sizeGB": 2.1,
  "status": "可用"
}
```

训练完成的任务由后端自动写入本列表（`status: 可用`），前端无需额外调用。本模块不提供模型选择功能，前端固定使用最新可用权重（基座恒为 Qwen2.5-3B-Instruct）。

---

### 3.5 对话模块

#### GET /api/v1/domains/{domainId}/chat/sessions · 会话列表（FR-15）

响应 `data.list[]`：

```json
[
  { "id": "medical-s-1", "title": "临床诊疗能力验证", "model": "MEDICAL-Qwen2.5-3B-v2.1", "turns": 6 }
]
```

#### POST /api/v1/domains/{domainId}/chat/sessions · 新建会话

请求：`{ "model": "MEDICAL-Qwen2.5-3B-v2.1" }` → 响应 `data`：完整 Session 对象（同上）。

#### GET /api/v1/chat/sessions/{sessionId}/messages · 历史消息

响应 `data.list[]`：

```json
[
  { "role": "user",      "content": "患者肌酐 320μmol/L……如何调整用药？", "time": "10:24" },
  { "role": "assistant", "content": "基于医疗领域知识的分析……",         "time": "10:24" }
]
```

#### POST /api/v1/chat/sessions/{sessionId}/messages · 发送消息（推荐 SSE 流式）

对应页面：对话窗口（FR-14）。两种实现任选其一，前端优先适配流式：

**方案 A · SSE（推荐）**：`Accept: text/event-stream`，请求体同方案 B。事件序列：

```
event: delta
data: {"content": "基于"}

event: delta
data: {"content": "医疗领域"}

event: done
data: {"messageId": "msg-88", "time": "10:25"}
```

**方案 B · 普通同步**：

请求：`{ "content": "患者肌酐 320μmol/L……如何调整用药？" }`

响应 `data`：

```json
{ "role": "assistant", "content": "基于医疗领域知识的分析……", "time": "10:25" }
```

多轮上下文由后端按 `sessionId` 维护（前端不重发历史），异常时返回明确错误，例如 `code: 41004, message: "模型加载中，请稍后再试"`。

---

### 3.6 评测模块

#### POST /api/v1/domains/{domainId}/evaluations · 创建评测任务

对应页面：配置评测任务表单（FR-16）。

请求：

```json
{
  "modelId": "medical-m-1",
  "testSetId": "medical-ds-3",
  "testSetVersion": "v1.0.2"
}
```

响应 `data`：`{ "evaluationId": "medical-ev-4" }`

`modelId` 默认使用该领域最新可用权重，前端不提供模型选择。

#### GET /api/v1/domains/{domainId}/evaluations · 评测记录列表

对应页面：评测记录表格（FR-18）。支持分页。

响应 `data.list[]`：

```json
{
  "id": "medical-ev-1",
  "model": "MEDICAL-Qwen2.5-3B-v2.1",
  "testSet": "基准测试集 v1.0.2",
  "status": "完成",
  "composite": 84,
  "dims": [92, 80, 87, 90, 78, 84],
  "finished": "2026-08-30 16:22"
}
```

**`dims` 固定 6 项**，顺序与 2.5 节评测维度一致；`composite` 为六项综合分（0-100 整数），由后端按权重计算（FR-19）。评测为异步任务，运行中任务本接口同样返回，前端轮询至 `完成` / `失败`。

---

### 3.7 跨领域对比模块

#### GET /api/v1/compare?domains=medical,legal,finance · 多领域最佳评测结果

对应页面：多领域对比页（FR-20）。

响应 `data.list[]`：

```json
[
  {
    "domainId": "medical",
    "domainName": "医疗",
    "accent": "#0B8A6D",
    "model": "MEDICAL-Qwen2.5-3B-v2.1",
    "composite": 84,
    "dims": [92, 80, 87, 90, 78, 84]
  }
]
```

每个领域取综合评分最高的一次评测结果；`domains` 省略时返回全部领域。

---

### 3.8 系统管理模块（仅 admin）

以下接口对 `role != admin` 的 token 返回 `403`（对应安全需求 2.2.4）。

#### GET /api/v1/admin/gpus · GPU 资源状态

响应 `data.list[]`：

```json
[
  { "id": "GPU-01", "model": "A100-80G", "used": 68, "task": "legal-LoRA-r32-e2" }
]
```

`used` 为显存占用百分比（0-100）。

#### GET /api/v1/admin/users · 用户列表

响应 `data.list[]`：

```json
[
  { "name": "researcher01", "role": "user", "domains": "医疗 / 金融", "lastLogin": "2026-09-01 09:12" }
]
```

#### GET /api/v1/admin/overview · 各领域资源占用

响应 `data.list[]`：

```json
[
  { "domainId": "medical", "datasets": 3, "models": 3, "storageGB": 43.6 }
]
```

#### PUT /api/v1/admin/config · 保存系统配置

请求：

```json
{
  "maxConcurrentTraining": 2,
  "evaluationRetentionDays": 180,
  "openRegistration": true
}
```

响应 `data` 为更新后的完整配置对象。

---

## 四、数据字典（与前端 `src/types.ts` 一致）

| 类型 | 字段 | 类型 | 说明 |
|---|---|---|---|
| Dataset | id / name / version / rows / updated / quality / splits | — | rows 为样本数；quality 为 0-100 质量分 |
| TrainTask | id / name / baseModel / dataset / status / progress / loss / evalLoss / started | — | progress 为 0-100；baseModel 恒为 Qwen2.5-3B-Instruct |
| DomainModel | id / name / baseModel / trainedOn / sizeGB / status | — | — |
| EvalTask | id / model / testSet / status / composite / dims / finished | — | dims 长度固定 6 |
| ChatMsg | role / content / time | — | role ∈ `user` `assistant` |

## 五、联调配置

开发期在 `vite.config.ts` 中开启代理即可无缝联调：

```ts
server: {
  port: 5173, host: true,
  proxy: {
    '/api': { target: 'http://<后端地址>:<端口>', changeOrigin: true }
  }
}
```

前端当前数据全部来自 `src/data/mock.ts`，联调时按页面逐模块将 mock 调用替换为上述接口即可，数据结构无需改动。
