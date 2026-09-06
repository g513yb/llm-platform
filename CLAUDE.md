# CLAUDE.md — 多域 LLM 微调与评测平台

## 项目是什么
FastAPI + React(Vite/TS) + PyTorch + HuggingFace Transformers + PEFT(LoRA) 的多领域大模型训练与评测平台。完整闭环：**选领域 → 数据处理 → LoRA微调 → 保存权重 → 复用对话 → 多维度评测 → 跨领域对比**。

当前进度：**Sprint 0-5 全部完成**——工作台 + Qwen2.5-7B 流式对话（0）+ 数据处理 12 种 schema + Alpaca 输出（1）+ LoRA 微调与权重保存（3）+ 权重复用对话（4）+ CMB-Exam 多维度评测（5）。跨领域对比页为后续。

## 关键设计
- **极简三文件数据处理**：无预设引擎/阶段级联/资源表；`server/data_pipeline/{__init__,readers,io}.py`。`readers.py` 的 `SCHEMAS` 是单一事实来源（在此查看支持哪些数据集及其全部键）。
- **领域仅标注**：领域（医疗/法律/金融/教育）不影响数据处理逻辑，实际处理只关注 schema；领域仅用于输出文件命名（`{slug}_alpaca.jsonl`）。
- **内部统一格式 = messages**：`[{role, content}, ...]`（引擎契约，与对话 Tab 一致）。`readers` 按 schema 自动识别多种输入（Alpaca/ShareGPT/CSV/CMB/MedQA/Toyhom/fingpt/MMLU/CMMLU 等），`_parse_clin`/`_parse_mcq`/`_parse_qa` 转成 messages。
- **训练输出 = Alpaca**：`io.messages_to_alpaca()` 落盘 `data/<slug>_alpaca.jsonl`（`{instruction,input,output}`）。运行时对话仍用 messages/Qwen chat 模板。
- **LoRA 训练**：`training.py` 的 `SFTDataset` 用 Qwen chat template 构建 prompt/full，prompt 部分 label=-100，仅对 assistant 段算 loss；按 `config.TRAIN_QUANTIZATION`（4bit/8bit/none）选量化，4bit/8bit 走 `prepare_model_for_kbit_training` + LoRA，none 走 bf16/fp16 全精度。本地 4070 8GB + Qwen2.5-3B-Instruct 4bit QLoRA；云端 4090 24GB + Qwen2.5-7B-Instruct。任务管理 `JOBS` dict + `jobs.json` 持久化，线程异步训练，服务重启时运行中任务标记"已终止"。
- **权重管理**：训练完成落盘 `server/adapters/<id>/`，`index.json` 登记；`/api/adapters` 列表、`/api/adapters/load` 热切换、`/api/adapters/active` 查当前。对话/评测共用 `infer_model`，切权重时加 `adapter_lock` 串行。
- **CMB-Exam 评测**：`eval_runner.py` 完整重现 CMB 12 项处理细节（option_str 过滤、两步 format、左 padding 切 prompt、多采样投票、match_choice 正则回退、父类准确率=子类算术平均等）；`evaluation.py` 仿训练任务管理，复用 `infer_model`，支持 few-shot（从 `cmb_val_merge.json` 选示例）。默认评测数据 `data/reference/medical/eval/`（11200 题）。

## 目录（要点）
- `server/app.py`：FastAPI 后端入口（uvicorn 启动 :8000；`MODEL_NAME`/`PORT` 环境变量可覆盖，同目录导入 `training`/`evaluation`/`eval_runner`/`data_pipeline`/`config`，须在 `server/` 下运行）。22 个 `/api/*` 端点：health/datasets(6)/train(5)/adapters(3)/chat/eval(6)。
- `server/config.py`：MODEL_NAME(env可覆盖)/FORCE_DEVICE/QUANTIZATION/TRAIN_QUANTIZATION/GENERATION/DOMAINS/DOMAIN_SLUGS/DATA_DIR/PROJECT_ROOT。
- `server/data_pipeline/`：`__init__.py`（`run_pipeline`/`inspect` 门面 + `PipelineSummary`）/ `readers.py`（`SCHEMAS` + `read_all` + `_parse_*`）/ `io.py`（`messages_to_alpaca` + `write_outputs`）。
- `server/domain.py`：领域注册表（labels/describe/slug，从 config 读取）。
- `server/training.py`：LoRA 训练任务管理（`SFTDataset` + `JOBS` + `jobs.json` + 线程异步）；`server/evaluation.py`：评测任务管理（仿 training，复用 `infer_model`）；`server/eval_runner.py`：CMB-Exam 评测核心（12 项处理细节 + 分层计分）。
- `server/chat.py`/`model_manager.py`：对话与模型加载；`server/adapters/`：LoRA 权重目录（`index.json` 登记）。
- `frontend/`：React+Vite+TS 前端（`npm run dev` :5173 / `npm run build` → dist/）；9 页：Overview/DomainSelect/Workspace/Chat/Datasets/Training/Evaluation/Compare/Admin；前后端契约见 `frontend/API.md`（注意：API.md 早期写的 `/api/v1` 前缀与鉴权未实现，实际为 `/api/*` 无鉴权）。
- `scripts/prepare_datasets.py`：一键数据准备（参考数据集转换）；`start-dev.ps1`：前后端一键无窗口启动 + Stop/存活探测。
- `docs/DATASETS.md`（数据集用法）、`docs/开发环境配置说明.md`（部署与环境）。

## 常用命令
- 云端部署（本机）：先 `git push origin main`，再 `./deploy.sh`（ssh 让云端 `git clone/pull` 远程仓库同步代码 + 装依赖）、`./deploy.sh start`（后台启动）、`./deploy.sh logs`（看日志）；本机 `ssh -N -L 8000:localhost:8000 autodl` 转发后端，前端本地 `npm run dev` 联调或托管 `dist/`。代码不本地直传，统一走 GitHub 仓库；浅克隆 `--depth=1` + 稀疏检出仅拉运行所需（`SPARSE_PATHS` 白名单，排除 docs/测试/本机脚本等）。
- 云端手启：`bash run.sh` 或 `bash start_app.sh`。
- 本机无窗口启停（华为云码道 IDE）：`./start-dev.ps1`（后台启前后端 + 日志落文件）、`./start-dev.ps1 -Stop`（停）。避免弹终端窗口。
- **本地纯 CPU 验证**（无需 GPU/云）：`cd D:\VscodeWorkplace\llm-platform && PYTHONIOENCODING=utf-8 .venv-verify/Scripts/python -c "import sys; sys.path.insert(0,'server'); from data_pipeline import run_pipeline; ..."`（`.venv-verify` 仅 pandas/numpy）。
- Git：`git add -A && git commit -m "…" && git push origin main`；仓库 `https://github.com/g513yb/llm-platform`；`gh` CLI 已装（`C:\Program Files\GitHub CLI\gh.exe`）。

## 数据流（数据处理）
`run_pipeline(domain, file_paths)`：
`read_all` 逐条按 schema 优先级尝试 `_parse_clin`（病例问答 QA_pairs）→ `_parse_mcq`（选择题 question+options）→ `_parse_qa`（问答 Alpaca/DISC-Law/CrimeKG/Huatuo/Toyhom）→ 识别失败计入 dropped → `io.write_outputs` 落盘 Alpaca。返回 `PipelineSummary(total, kept, dropped, type_counts, output_files, preview)`。
`inspect(domain, file_paths, limit=100)` 轻量识别不落盘，返回 `(summary, error_msg)`。

## 数据流（训练）
`training.run_training(task_id, dataset_path, rank, lr, epochs, batch, ...)`：
读 `data/<slug>_alpaca.jsonl` → `SFTDataset` 用 Qwen chat template 构建 prompt/full，prompt 段 label=-100 → 4bit 量化 + `prepare_model_for_kbit_training` + LoRA(rank) → Trainer 训练 → 落盘 `server/adapters/<task_id>/` + `register_adapter` 登记 `index.json`。前端 `Training.tsx` 接 `/api/train` 真接口（创建/列表/状态/停止/删除 + LossCurve）。**禁止并发训练**（前后端双重防护防显存 OOM）。

## 数据流（评测）
`evaluation.run_eval(task_id, get_model_fn, test_path, answer_path, use_cot, batch_size, gen_config, adapter_label, n_shot=0, val_path=None)`：
`load_test_data` 读 CMB test+answer → 可选 few-shot 从 `cmb_val_merge.json` 选示例 → `run_inference_batch` 推理（左 padding 切 prompt）→ `extract_ans` + `match_choice` 正则回退 → `score_layered` 分层计分（父类=子类算术平均）→ `composite_score` 综合。前端 `Evaluation.tsx` 接 `/api/eval` 真接口（创建/列表/结果/停止/删除 + RadarChart/ScoreRing），评测前先 `/api/adapters/load` 切权重。

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
- **训练并发**：禁止同时跑多个训练任务，前后端双重防护（按钮禁用 + 后端状态检查）防显存 OOM。
- **评测 CMB 12 项细节**：option_str 用 `len(v)>1` 过滤、两步 format、左 padding 切 prompt、多采样投票、match_choice 正则回退、父类准确率=子类算术平均（非总数比）等，详见 `eval_runner.py` 文件头注释。
- 开发时本地验证用 `.venv-verify`，`server/` 需 GPU 用云。
