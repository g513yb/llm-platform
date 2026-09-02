# CLAUDE.md — 多域 LLM 微调与评测平台

## 项目是什么
Gradio(BLOCKS) + PyTorch + HuggingFace Transformers + PEFT(LoRA) 的多领域大模型训练与评测平台。完整闭环：**选领域 → 数据治理 → LoRA微调 → 保存权重 → 复用对话 → 多维度评测 → 跨领域对比**。

当前进度：**Sprint 0（工作台 + Qwen2.5-7B 流式对话）+ Sprint 1（数据治理 + 四领域数据集 + Alpaca 输出）完成**；训练/权重/评测为后续 Sprint。

## 关键设计
- **内部统一格式 = ShareGPT**：`WorkItem.messages=[{"role","content"}...]`（引擎契约）。`readers` 接受多种输入（Alpaca/ShareGPT/CSV/CMB/MedQA/Toyhom/fingpt/MMLU/CMMLU/纯文本等），`_normalize` 全部转成 messages；清洗/质控阶段遍历 messages。
- **训练输出 = Alpaca**：`io.messages_to_alpaca()` 落盘 `data/<slug>_alpaca.json/.jsonl`（`{instruction,input,output}`）；`config.OUTPUT_FORMAT="alpaca"`，可切回 `"sharegpt"`。运行时对话仍用 messages/Qwen chat 模板。
- **领域预设 = 资源即知识**：`resources/<slug>/*.json`（deid/sections/terms/units/qc/structure/citation/numeric/options）+ `resources/<slug>/presets/<name>.json`（命名预设，可内嵌 `qc` 覆盖）。`domain_presets/` 引擎解释。**改资源即改规则，不改代码**。
- **每域双预设**：严格 `_cn`（结构/选项/数值要素）+ 宽松 `_qa`（`presets/qa.json`，`qc.mode:"pair"`；问答/情感/选择类）。`run_pipeline(..., preset=)` 选择。

## 目录（要点）
- `app.py`：入口（Gradio 启动；GPU 预热失败不阻断，纯 CPU 功能仍可用）。
- `config.py`：MODEL_NAME(env可覆盖)/DOMAINS/DOMAIN_SLUGS/DATA_DIR/RESOURCE_DIR/OUTPUT_FORMAT。
- `llm_platform/data_pipeline/`：`run_pipeline` 门面 / readers / cleaners / txt_generator / io。
- `llm_platform/domain_presets/`：engine / resources / stages_generic / stages_legal / __init__(STAGE_REGISTRY)。
- `llm_platform/ui/tabs/`：chat、data（真）；train/weights/eval（占位 stub）。
- `resources/{_shared,medical,legal,finance,education}/`；`docs/DATASETS.md`（数据集用法）、`docs/ENVIRONMENT.md`（部署）。

## 常用命令
- 云端部署（本机）：`./deploy.sh`（推码+装依赖）、`./deploy.sh start`（后台启动）、`./deploy.sh logs`（看日志）；本机 `ssh -N -L 7860:localhost:7860 autodl` 转发，浏览器 `http://localhost:7860`。
- 云端手启：`bash run.sh` 或 `bash start_app.sh`。
- **本地纯 CPU 验证**（无需 GPU/云）：`cd D:\claude\llm-platform && PYTHONIOENCODING=utf-8 .venv-verify/Scripts/python - <<'PY' … PY`（`.venv-verify` 仅 pandas/numpy）。
- Git：`git add -A && git commit -m "…" && git push origin main`；仓库 `https://github.com/g513yb/llm-platform`；`gh` CLI 已装（`C:\Program Files\GitHub CLI\gh.exe`）。

## 数据流（数据治理）
`run_pipeline(domain_label, file_paths, texts, preset, min_len, max_len, dedup, score_cutoff)`：
reader(多格式→messages) → generic_clean → preset.run(阶段级联) → `_pick_drop`(drop级issue / domain_score<cutoff / 长度越界) → dedupe → io(messages→Alpaca)。返回 `PipelineSummary`。

## 数据集 → 预设（详见 docs/DATASETS.md）
- 选择题/数值/文书类 → 严格 `_cn`：MMLU、CMMLU、CMB-Exam、MedQA、FinEval-选择、CMB-Clin、Chinese-Law-Doc(文书)、金融研报。
- 问答/情感/自由类 → 宽松 `_qa`：Toyhom、Huatuo-26M、DISC-Law-SFT、LawBench(问答·摘要)、fingpt-sentiment、FinEval-QA、EduChat。

## 常见改动模式
- 加数据集格式：`readers.py` 加 `_normalize`/`_read_csv` 分支。
- 加命名预设：`resources/<slug>/presets/<name>.json`（stages + 可选 `qc`）；`config` 无需改。
- 加阶段：`stages_generic.py` 加 `Stage` 子类 + `domain_presets/__init__.py` 注册进 `STAGE_REGISTRY` + preset.json 加 stage。
- 加领域：`resources/<slug>/`（表+presets）+ `config.DOMAINS/DOMAIN_SLUGS` + `domain.py`。

## 坑（重要）
- **法律 preset 计分**：`QualityScoreStage` 必须优先按 `doc_type_checks` 对应 checks 计分（勿改回顶层 `checks`，否则法律全 0 分误杀；先前的 bug 曾被 `score_cutoff=0.0` 掩盖）。
- **MCQ-CSV 分支先行**：`question+A..D+answer` 判定须在通用"问答列"之前（否则丢选项）。
- 中文编码 GBK（Toyhom CSV）；多选答案 `_norm_answer`；medical 缺"主诉+诊断"→严格预设会丢（用宽松）。
- 复数键兼容：`option/options`、`answer/answer_idx/response`、`input/output`。
- `OUTPUT_FORMAT` 默认 `alpaca`；开发时本地验证用 `.venv-verify`，UI/需 GPU 用云。
