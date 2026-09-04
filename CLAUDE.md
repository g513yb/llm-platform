# CLAUDE.md — 多域 LLM 微调与评测平台

## 项目是什么
FastAPI + React(Vite/TS) + PyTorch + HuggingFace Transformers + PEFT(LoRA) 的多领域大模型训练与评测平台。完整闭环：**选领域 → 数据处理 → LoRA微调 → 保存权重 → 复用对话 → 多维度评测 → 跨领域对比**。

当前进度：**Sprint 0（工作台 + Qwen2.5-7B 流式对话）+ Sprint 1（数据处理 + 四领域数据集 + Alpaca 输出）完成**；训练/权重/评测为后续 Sprint。

## 关键设计
- **极简三文件数据处理**：无预设引擎/阶段级联/资源表；`server/data_pipeline/{__init__,readers,io}.py`。`readers.py` 的 `SCHEMAS` 是单一事实来源（在此查看支持哪些数据集及其全部键）。
- **领域仅标注**：领域（医疗/法律/金融/教育）不影响数据处理逻辑，实际处理只关注 schema；领域仅用于输出文件命名（`{slug}_alpaca.jsonl`）。
- **内部统一格式 = messages**：`[{role, content}, ...]`（引擎契约，与对话 Tab 一致）。`readers` 按 schema 自动识别多种输入（Alpaca/ShareGPT/CSV/CMB/MedQA/Toyhom/fingpt/MMLU/CMMLU 等），`_parse_clin`/`_parse_mcq`/`_parse_qa` 转成 messages。
- **训练输出 = Alpaca**：`io.messages_to_alpaca()` 落盘 `data/<slug>_alpaca.jsonl`（`{instruction,input,output}`）。运行时对话仍用 messages/Qwen chat 模板。

## 目录（要点）
- `server/app.py`：FastAPI 后端入口（uvicorn 启动 :8000；`MODEL_NAME`/`PORT` 环境变量可覆盖，同目录导入 `training`/`data_pipeline`/`config`，须在 `server/` 下运行）。
- `server/config.py`：MODEL_NAME(env可覆盖)/FORCE_DEVICE/QUANTIZATION/GENERATION/DOMAINS/DOMAIN_SLUGS/DATA_DIR/PROJECT_ROOT。
- `server/data_pipeline/`：`__init__.py`（`run_pipeline`/`inspect` 门面 + `PipelineSummary`）/ `readers.py`（`SCHEMAS` + `read_all` + `_parse_*`）/ `io.py`（`messages_to_alpaca` + `write_outputs`）。
- `server/domain.py`：领域注册表（labels/describe/slug，从 config 读取）。
- `server/training.py`：LoRA 训练任务管理；`server/chat.py`/`model_manager.py`：对话与模型加载。
- `frontend/`：React+Vite+TS 前端（`npm run dev` :5173 / `npm run build` → dist/）；前后端契约见 `frontend/API.md`。
- `docs/DATASETS.md`（数据集用法）、`docs/开发环境配置说明.md`（部署与环境）。

## 常用命令
- 云端部署（本机）：先 `git push origin main`，再 `./deploy.sh`（ssh 让云端 `git clone/pull` 远程仓库同步代码 + 装依赖）、`./deploy.sh start`（后台启动）、`./deploy.sh logs`（看日志）；本机 `ssh -N -L 8000:localhost:8000 autodl` 转发后端，前端本地 `npm run dev` 联调或托管 `dist/`。代码不本地直传，统一走 GitHub 仓库；浅克隆 `--depth=1` + 稀疏检出仅拉运行所需（`SPARSE_PATHS` 白名单，排除 docs/测试/本机脚本等）。
- 云端手启：`bash run.sh` 或 `bash start_app.sh`。
- **本地纯 CPU 验证**（无需 GPU/云）：`cd D:\VscodeWorkplace\llm-platform && PYTHONIOENCODING=utf-8 .venv-verify/Scripts/python -c "import sys; sys.path.insert(0,'server'); from data_pipeline import run_pipeline; ..."`（`.venv-verify` 仅 pandas/numpy）。
- Git：`git add -A && git commit -m "…" && git push origin main`；仓库 `https://github.com/g513yb/llm-platform`；`gh` CLI 已装（`C:\Program Files\GitHub CLI\gh.exe`）。

## 数据流（数据处理）
`run_pipeline(domain, file_paths)`：
`read_all` 逐条按 schema 优先级尝试 `_parse_clin`（病例问答 QA_pairs）→ `_parse_mcq`（选择题 question+options）→ `_parse_qa`（问答 Alpaca/DISC-Law/CrimeKG/Huatuo/Toyhom）→ 识别失败计入 dropped → `io.write_outputs` 落盘 Alpaca。返回 `PipelineSummary(total, kept, dropped, type_counts, output_files, preview)`。
`inspect(domain, file_paths, limit=100)` 轻量识别不落盘，返回 `(summary, error_msg)`。

## 支持的数据集（12 种，详见 docs/DATASETS.md）
- **选择题（mcq）**：CMB-Exam、MedQA、CMMLU、MMLU、FinEval-MCQ
- **病例问答（clin）**：CMB-Clin（一份病历多组 QA）
- **问答（qa）**：CrimeKG-QA、DISC-Law-Pair、DISC-Law-Triplet、FinGPT-sentiment、LawBench、Huatuo-26M、Toyhom

## 常见改动模式
- 加数据集格式：`readers.py` 的 `SCHEMAS` 加新 schema + 对应 `_parse_*` 分支，`read_all` 自动覆盖。
- 加领域：`config.DOMAINS`/`DOMAIN_SLUGS` 加映射（领域仅标注，不需建资源表）。

## 坑（重要）
- **MCQ-CSV 分支先行**：`question+A..D+answer` 判定须在通用"问答列"之前（否则丢选项）。
- **CSV 编码探测**：`_sniff_csv_encoding` 用 incremental decoder 避免块截断在多字节字符中间误判（utf-8-sig 优先，回退 gb18030）。
- **CrimeKG answers**：是多段列表，拼接还原而非只取首条。
- **DISC-Law 英文翻译**：`_strip_english_translation` 去除英文占比>70%的段落。
- **字段大小写**：CMMLU header 为 `Question`/`Answer`（首字母大写），`_parse_mcq` 做大小写变体查找。
- 复数键兼容：`option/options`、`answer/answer_idx/response`、`input/output`。
- 开发时本地验证用 `.venv-verify`，`server/` 需 GPU 用云。
