# 多域 LLM 微调与评测平台

基于 **PyTorch + HuggingFace Transformers + PEFT(LoRA)** 的多领域大模型训练与评测平台。核心是一条完整闭环：**选领域 → 处理数据 → LoRA 微调 → 保存权重 → 复用对话 → 多维度评测 → 跨领域对比**。

> 当前进度：**Sprint 0-5 全部完成**（工作台 + 流式对话 + 数据处理 + LoRA 训练 + 权重管理 + CMB-Exam 评测）；跨领域对比页为后续 Sprint。
>
> 📄 开发环境、部署链路与全部配置项见 **[docs/开发环境配置说明.md](./docs/开发环境配置说明.md)**。
> 📄 支持的数据集与获取/字段用法见 **[docs/DATASETS.md](./docs/DATASETS.md)**。

## 全貌（功能全景）

```
┌─ React 工作台（顶部选领域 → 进入工作台）
│   ├─ 对话        ✅ 加载 Qwen2.5-7B-Instruct，多轮对话 + 逐字流式（需 GPU）
│   ├─ 数据处理    ✅ 上传语料 → schema 自动识别 → Alpaca 落盘 + 统计
│   ├─ LoRA训练    ✅ 4bit 量化 + LoRA 微调，云端 4090 24GB 跑 Qwen2.5-7B，任务管理 + Loss 曲线
│   ├─ 权重管理    ✅ 训练完成落盘 adapters/，热切换 + 复用对话/评测
│   └─ 多维度评测  ✅ CMB-Exam 选择题评测（11200 题），分层计分 + few-shot + 雷达图
└─ 服务层（纯 CPU，不挂卡可跑）
    └─ data_pipeline/   读入 → schema 自动识别 → messages → Alpaca 落盘
```

## 已实现功能

### Sprint 0 · 基座 + 工作台
- **对话 Tab**：加载基座 `Qwen/Qwen2.5-7B-Instruct`，多轮上下文 + 流式输出；模型配置驱动（`config.MODEL_NAME` 一处换）。
- **工作台骨架**：顶部领域下拉（医疗/法律/金融/教育）→ 进入工作台 → 多 Tab 导航。

### Sprint 1 · 数据处理
- **输入格式**（`.json/.jsonl/.csv/.parquet`）：reader 按 schema 自动识别，统一转内部 messages 格式
  - **选择题（mcq）**：CMB-Exam、MedQA、CMMLU、MMLU、FinEval-MCQ（`question+options+answer`）
  - **病例问答（clin）**：CMB-Clin（`description+QA_pairs`，一份病历多组 QA）
  - **问答（qa）**：CrimeKG-QA、DISC-Law-Pair/Triplet、FinGPT-sentiment、LawBench、Huatuo-26M、Toyhom
  - CSV 编码自动探测（utf-8-sig → gb18030，incremental decoder 避免截断误判）
- **领域仅标注**：领域（医疗/法律/金融/教育）不影响处理逻辑，仅用于输出文件命名（`{slug}_alpaca.jsonl`）
- **落盘**：`data/<slug>_alpaca.jsonl`，统一为 Alpaca `{instruction,input,output}`（训练用）
- **统计**：总数/保留/丢弃 + 类型分布 + 前 20 条预览
- **后端端点**：`POST /api/datasets/upload`（inspect 轻量识别不落盘）、`POST /api/datasets/process`（run_pipeline 落盘）、`GET /api/datasets/output/{filename}`（查看输出文件）

### Sprint 3 · LoRA 微调 + 权重保存
- **量化可切**：按 `config.TRAIN_QUANTIZATION`（4bit/8bit/none）选训练量化，4bit/8bit 走 `prepare_model_for_kbit_training` + LoRA，none 走 bf16/fp16 全精度。本地 4070 8GB + Qwen2.5-3B-Instruct 4bit QLoRA；云端 4090 24GB + Qwen2.5-7B-Instruct bf16 全精度 LoRA。
- **任务管理**：`JOBS` dict + `jobs.json` 持久化，线程异步训练，服务重启时运行中任务标记"已终止"。
- **权重落盘**：训练完成落盘 `server/adapters/<task_id>/`，`index.json` 登记。
- **前端**：`Training.tsx` 接 `/api/train` 真接口（创建/列表/状态/停止/删除 + LossCurve）。
- **并发保护**：禁止同时跑多个训练任务，前后端双重防护（按钮禁用 + 后端状态检查）防显存 OOM。

### Sprint 4 · 权重复用对话
- **权重管理端点**：`/api/adapters`（列表）、`/api/adapters/active`（当前）、`/api/adapters/load`（热切换）。
- **复用 infer_model**：对话/评测共用 `infer_model`，切权重时加 `adapter_lock` 串行避免冲突。

### Sprint 5 · CMB-Exam 多维度评测
- **评测核心**：`eval_runner.py` 完整重现 CMB 12 项处理细节（option_str 过滤、两步 format、左 padding 切 prompt、多采样投票、match_choice 正则回退、父类准确率=子类算术平均等）。
- **任务管理**：`evaluation.py` 仿训练任务管理，复用 `infer_model`，支持 few-shot（从 `cmb_val_merge.json` 选示例）。
- **默认评测数据**：`data/reference/medical/eval/`（11200 题）。
- **前端**：`Evaluation.tsx` 接 `/api/eval` 真接口（创建/列表/结果/停止/删除 + RadarChart/ScoreRing），评测前先 `/api/adapters/load` 切权重。

## 目录结构

```
llm-platform/
├── server/                    # FastAPI 后端（须在此目录下运行 python app.py）
│   ├── app.py                 # 入口：模型加载 + LoRA 推理/训练 + 流式对话（MODEL_NAME/PORT env 可覆盖）
│   ├── config.py              # 唯一配置源：MODEL_NAME / DOMAINS / DOMAIN_SLUGS / DATA_DIR / ...
│   ├── domain.py              # 领域注册表：labels / describe / slug
│   ├── training.py            # LoRA 训练任务管理（SFTDataset + JOBS + jobs.json + 线程异步）
│   ├── evaluation.py          # 评测任务管理（仿 training，复用 infer_model）
│   ├── eval_runner.py         # CMB-Exam 评测核心（12 项处理细节 + 分层计分）
│   ├── chat.py                # 对话管线
│   ├── model_manager.py       # 模型懒加载
│   ├── data_pipeline/         # 数据处理门面（极简三文件）
│   │   ├── __init__.py        # run_pipeline / inspect → PipelineSummary
│   │   ├── readers.py         # SCHEMAS（单一事实来源）+ read_all + _parse_clin/_parse_mcq/_parse_qa
│   │   └── io.py              # messages → Alpaca 落盘
│   └── adapters/              # LoRA 权重目录
├── frontend/                  # React+Vite+TS 前端（npm run dev :5173 / build → dist/）
│   ├── src/                   # 页面/组件/类型/模拟数据
│   ├── API.md                 # 前后端接口契约
│   └── package.json
├── data/                      # 数据处理产物（alpaca jsonl）← gitignore
├── requirements.txt           # 云端运行依赖（不重装 AutoDL 自带 CUDA torch）
├── run.sh                     # AutoDL 启动脚本（cd server && python app.py）
├── start_app.sh               # 云端后台启动脚本（setsid 脱离会话）

└── docs/                      # 文档
    ├── DATASETS.md            # 数据集用法
    └── 开发环境配置说明.md     # 部署与环境
```

## 快速开始

### 云端（AutoDL）
1. **同步代码**：代码不经本地直传，统一走 GitHub 远程仓库。本机 `git push origin <branch>` + `git push github <branch>` 后，ssh 让云端拉取（完整命令见 memory `project_cloud_sync_commands`）：
   ```bash
   ssh autodl 'source /etc/network_turbo && cd /root/autodl-tmp/llm-platform && git fetch origin <branch> && git reset --hard origin/<branch>'
   ```
2. **装依赖 + 启动**（云端手启，或 ssh 远程调 start_app.sh）：
   ```bash
   cd /root/autodl-tmp/llm-platform && bash run.sh
   # = pip install -r requirements.txt && cd server && python app.py
   ```
   > AutoDL 镜像自带 CUDA torch，`run.sh` 只补装缺失库，不重装 torch。
3. **访问**（本地终端端口转发，只转发不占 GPU）：
   ```bash
   ssh -N -L 8000:localhost:8000 autodl     # 转发 FastAPI 后端
   # 前端：本机 frontend/ 下 npm run dev → http://localhost:5173 联调；或托管 dist/ 静态文件
   ```

### 开发机模式（共用一个支持 `.venv-verify` 的轻量环境）
- 纯 CPU 的数据处理管道**可本地验证**，不必挂卡/开云：
  ```bash
  cd D:\VscodeWorkplace\llm-platform
  set PYTHONIOENCODING=utf-8
  .venv-verify\Scripts\python -c "import sys; sys.path.insert(0,'server'); from data_pipeline import run_pipeline; print(run_pipeline('医疗', ['data.jsonl']))"
  ```
  > `.venv-verify` 只装了 pandas/numpy（几十 MB）；Windows 控制台打印中文可能乱码，`set PYTHONIOENCODING=utf-8` 可避免。
- **推理/训练需要 GPU**（聊天、模型加载）。本机若无 GPU，推理/训练只在云端跑。

### 本机 GPU 运行（可选，需 NVIDIA 独显 + 已下模型）

模型路径与量化走**环境变量**驱动（不污染云端默认）；本机 12GB 显存跑 7B 用 4bit 量化。

```bat
rem ① 一次性建本地环境（仅在有 GPU 的机器上；会装 CUDA torch + requirements + bitsandbytes）
setup_local.bat

rem ② 指定本地模型目录（或直接把路径填进 run_local.bat）
set MODEL_NAME=D:\models\Qwen2.5-7B-Instruct

rem ③ 启动（内部设 QUANTIZATION=4bit）
run_local.bat
rem → 浏览器打开 http://127.0.0.1:8000
```

### 切换模型
`server/config.py`：
```python
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"   # 可换同系列 1.5B/14B；或本机本地路径（也可用 env MODEL_NAME 覆盖）
QUANTIZATION = "none"                     # "none" | "8bit" | "4bit"（8bit/4bit 需装 bitsandbytes + GPU；12GB 跑 7B 用 4bit）
FORCE_DEVICE = None                       # None=自动探测；"cuda"/"cpu" 强制（本地调试）
```

## 数据处理用法

进入「数据处理」Tab：
1. 选领域（医疗/法律/金融/教育）。
2. 上传文件（.csv/.json/.jsonl/.txt），后端 `inspect` 轻量识别格式并返回统计。
3. 点「处理」，`run_pipeline` 落盘 `data/<slug>_alpaca.jsonl`（`{instruction,input,output}`），返回统计 + 前 20 条预览。
4. 可点击输出文件查看完整内容。

命令行等价：
```python
import sys; sys.path.insert(0, "server")
from data_pipeline import run_pipeline
res = run_pipeline("医疗", file_paths=["病历.jsonl"])
print(res.kept, res.dropped, res.type_counts, res.output_files)   # 落盘 data/medical_alpaca.jsonl
```

## 数据处理如何扩展

- **加数据集格式**：在 `server/data_pipeline/readers.py` 的 `SCHEMAS` 加新 schema + 对应 `_parse_*` 分支，`read_all` 自动覆盖（按 `_parse_clin` → `_parse_mcq` → `_parse_qa` 优先级尝试）。
- **加领域**：在 `server/config.py` 的 `DOMAINS`/`DOMAIN_SLUGS` 加映射（领域仅标注，不需建资源表）。

## 常见问题

- **`CUDA 不可用`**：在无 GPU 机器上跑。聊天/训练需 AutoDL GPU 实例；数据处理纯 CPU 无需。
- **聊天无卡也用不了**：FastAPI 后端启动时会加载模型，对话/训练需挂卡才可用。
- **无卡能看到数据处理但点对话报错**：正常，属预期。
- **首次权重下载慢**：AutoDL 开「学术加速」。
- **版本冲突**：AutoDL 镜像 torch 较旧时，去掉 `requirements.txt` 里 `transformers` 的版本号再 `pip install -U transformers fastapi accelerate`。
- **本地改代码要上云**：`git push origin <branch>` + `git push github <branch>` 后，ssh 让云端 `git fetch + reset --hard`（带学术加速）+ 装依赖 + 重启；完整命令见 memory `project_cloud_sync_commands`。

## 路线图

| Sprint | 内容 | 状态 |
|---|---|---|
| 0 | 工作台 + Qwen 流式对话 | ✅ 完成 |
| 1 | 数据处理 + 12 种数据集 schema + Alpaca 输出 | ✅ 完成 |
| 3 | LoRA 微调 + 自动保存权重 | ✅ 完成 |
| 4 | 权重复用对话 + 多轮记忆加强 | ✅ 完成 |
| 5 | 多维度评测（CMB-Exam） | ✅ 完成 |
| 6 | 跨领域对比 | ⏳ 占位 |
