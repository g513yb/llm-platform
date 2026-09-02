# 多域 LLM 微调与评测平台

基于 **PyTorch + HuggingFace Transformers + PEFT(LoRA)** 的多领域大模型训练与评测平台。核心是一条完整闭环：**选领域 → 治理数据 → LoRA 微调 → 保存权重 → 复用对话 → 多维度评测 → 跨领域对比**。

> 当前进度：**Sprint 0 + Sprint 1 已完成**（工作台 + Qwen 流式对话 + 数据治理）；训练/权重/评测为后续 Sprint。
>
> 📄 开发环境、部署链路与全部配置项见 **[docs/ENVIRONMENT.md](./docs/ENVIRONMENT.md)**。
> 📄 支持的数据集与获取/字段/预设用法见 **[docs/DATASETS.md](./docs/DATASETS.md)**。

## 全貌（功能全景）

```
┌─ Gradio 工作台（顶部选领域 → 进入工作台）
│   ├─ 对话        ✅ 加载 Qwen2.5-7B-Instruct，多轮对话 + 逐字流式（需 GPU）
│   ├─ 数据治理    ✅ 上传/粘贴语料 → 清洗 + 领域预设 + 质量过滤 → ShareGPT 落盘 + 统计
│   ├─ LoRA训练    ⏳ 占位（后续 Sprint）
│   ├─ 权重管理    ⏳ 占位（后续 Sprint）
│   └─ 多维度评测  ⏳ 占位（后续 Sprint）
└─ 服务层（纯 CPU，不挂卡可跑）
    ├─ data_pipeline/   读入 → 通用清洗 → 领域预设 → 质量过滤 → 去重 → 落盘
    └─ domain_presets/  阶段化领域预设引擎（资源驱动：资源=知识）
```

## 已实现功能

### Sprint 0 · 基座 + 工作台
- **对话 Tab**：加载基座 `Qwen/Qwen2.5-7B-Instruct`，多轮上下文 + 流式输出；模型配置驱动（`config.MODEL_NAME` 一处换）。
- **工作台骨架**：顶部领域下拉（医疗/法律/金融/教育）→ 进入工作台 → 五个 Tab；新增 Tab = 建模块 + 追加进 `TAB_REGISTRY` 即插即用。

### Sprint 1 · 数据治理
- **输入格式**（`read_inputs`，`.json/.jsonl/.csv/.txt`）：
  - Alpaca：`{instruction, input(可选), output}`（或中文 `指令/输入/输出`）
  - ShareGPT：`{"messages":[{role,content}...]}`
  - CSV：`instruction/input/output` 列，或 `id/role/content` 长表、`ask/question+answer` 问答列；编码 `utf-8-sig → gbk → utf-8` 自动回退
  - **医疗数据集**：CMB-Exam(`question_type/option/answer`)、CMB-Clin(`QA_pairs`，一条→多条)、Toyhom(`department/title/ask/answer`)、MedQA(`options/answer_idx`)、Huatuo-26M(`question/response`)
  - **法律数据集**：DISC-Law-SFT(Alpaca)、LawBench(问答/摘要，法条检索/判决预测留评测)、Chinese-Law-Doc(raw 文书→法规抽条/判决书要点/合同要点)
  - **金融数据集**：FinEval(选择题/开放问答)、fingpt-sentiment-train(`input/output` 情感标签)；BloombergGPT 无公开数据集（仅论文）
  - **纯文本**：医疗/法律经 `txt_generator` **领域规则抽取** 自动合成 ShareGPT 问答对（见下）；其余领域纯文本暂不支持
- **清洗**：通用逐轮（编码/全半角/空白/去标签）+ 语料级去重（精确 sha1 + 近似 bigram Jaccard）
- **领域预设**：阶段化引擎级联跑（见下节）
- **质量过滤**：长度/重复/特殊字符/结构要素 + 领域质量分阈值 → 保留/丢弃（含原因直方图）
- **落盘**：`data/<slug>_sharegpt.jsonl` + `.json` + `<slug>_config.json`（参数可复现）
- **统计**：总数/保留/丢弃 + 每阶段处置数 + 丢弃原因分布 + 前 20 条明细（UI 三表）

### 领域预设（引擎 + 资源 = 知识即数据）
核心思想：**领域知识放在 `resources/<domain>/*.json`，由可复用引擎解释；改资源即改规则，无需改代码。**

- **引擎**（`domain_presets/`）：`Stage`（可插拔处理器）/ `WorkItem`（单样本）/ `Issue`（清理·标注·警告·丢弃）/ `DomainPreset`（有序 stage，由 preset.json 数据驱动）/ `PipelineCtx`（已编译资源）/ `StageStats`。
- **通用阶段**（`stages_generic`）：deid / section / terminology / units / completeness_qc / quality_score / marker_norm / numeric。
- **法律专属阶段**（`stages_legal`）：`DocTypeStage`（文书类型识别）+ `LegalStructureStage`（文号规范化 + 编章节条款项层级树 + 分部）。
- **医疗（深度）**：小节识别（主诉/现病史/过敏史/手术史/生命体征…，保序）、分层脱敏（姓名/复姓/身份证/手机/医保卡/就诊卡/机构，防误判）、术语接线（preserve + qd/bid→每日N次）、单位+化验值区间、跨小节一致性质检（诊断未在现病史 → warning）。医疗有**两个预设**：`medical_cn`（临床病历，严格，要求主诉/诊断）与 `medical_qa`（考试/问答，宽松，仅脱敏/术语/单位+质量分，用于 CMB/Toyhom）。
- **法律（深度）**：当事人脱敏（保留案号/文号/日期/法院名绝不脱敏）、文书分部、编章条层级、`doc_type_checks` 文档类型感知质控（判决书缺要素 → drop；中文日期也匹配）。法律有两个预设：`legal_cn`（文书，严格）与 `legal_qa`（问答/指令，宽松，用于 DISC-Law-SFT/LawBench 等）。
- **金融 / 教育**：同引擎 + 薄资源表。金融有 `finance_cn`（数值研报，强制数值+单位）与 `finance_qa`（问答/情感/选择题，宽松）；教育单预设（选项/答案规范化）。

**扩展一个新领域**：在 `resources/<slug>/` 下建 `preset.json`（stage 顺序）+ 各类资源表即可，其余不动。

## 目录结构

```
llm-platform/
├── app.py                     # 入口：构建 UI + 预热模型 + 启动（GPU 预热失败也不阻断，纯 CPU 功能仍可用）
├── config.py                  # 唯一配置源：MODEL_NAME / DOMAINS / DOMAIN_SLUGS / DATA_DIR / RESOURCE_DIR
├── requirements.txt           # 云端运行依赖（不重装 AutoDL 自带 CUDA torch）
├── run.sh                     # AutoDL 启动脚本
├── run.bat                    # 本机提示（需在云端跑 GPU）
├── deploy.sh                  # 一键推码到云端 + 装依赖 + 后台启动 / 看日志
├── start_app.sh               # 云端后台启动脚本（setsid 脱离会话）
├── samples/                   # 示例数据（仅开发测试，不进 UI 入口）
├── .venv-verify/              # 本地轻量 venv（仅 pandas，用于纯 CPU 管道本地验证）
├── resources/                 # 领域预设资源（知识即数据）
│   ├── _shared/               # deid / units 基础表
│   ├── medical/               # sections/deid/terms/units/qc/preset  ← 深度参考实现
│   ├── legal/                 # deid/sections/terms/structure/citation/qc/preset
│   ├── finance/               # numeric/qc/preset
│   └── education/             # options/qc/preset
└── llm_platform/
    ├── model_manager.py       # 懒加载单例 load_model()，设备/精度探测
    ├── chat.py                # 对话管线：apply_chat_template + generate + 流式
    ├── domain.py              # 领域注册表 / slug / 默认预设
    ├── data_pipeline/         # 数据治理门面
    │   ├── __init__.py        # run_pipeline(domain, file_paths, texts, …) → PipelineSummary
    │   ├── readers.py         # 输入归一化（Alpaca/ShareGPT/CSV/.txt）
    │   ├── cleaners.py        # 通用逐轮清洗 + 去重
    │   ├── txt_generator.py   # 纯文本 → 问答对（医疗/法律规则抽取）
    │   └── io.py              # 落盘 sharegpt jsonl/json + config.json
    ├── domain_presets/        # 阶段化领域预设引擎
    │   ├── engine.py          # Stage/WorkItem/Issue/DomainPreset/PipelineCtx/StageStats
    │   ├── resources.py       # ResourceBundle.load()（读 resources/、合并 shared、编译正则）
    │   ├── stages_generic.py  # 通用阶段
    │   ├── stages_legal.py    # DocTypeStage + LegalStructureStage
    │   └── __init__.py        # STAGE_REGISTRY / make_stage / build_preset / default_preset
    └── ui/
        ├── app_layout.py      # Blocks：领域下拉 + 进入工作台 + Tabs
        ├── placeholder.py     # 占位 Tab 渲染
        └── tabs/              # ★ 接缝：每个工作台 Tab 一个模块（TITLE + build(domain)）
            ├── __init__.py    # TAB_REGISTRY
            ├── chat_tab.py    # 对话（真）
            ├── data_tab.py    # 数据治理（真）
            └── train/weights/eval_tab.py  # 占位
```

## 快速开始

### 云端（AutoDL）
1. **传代码**：`scp`/JupyterLab/`git` 把本目录放到实例，如 `/root/autodl-tmp/llm-platform`（数据盘）。
2. **一键部署**（也可只用 `./deploy.sh` 反复推代码 + 重启）：
   ```bash
   cd /root/autodl-tmp/llm-platform && bash run.sh
   # = pip install -r requirements.txt && python app.py
   ```
   > AutoDL 镜像自带 CUDA torch，`run.sh` 只补装缺失库，不重装 torch。权重走 `/root/autodl-tmp/llm-platform/hf`。
3. **访问**（本地终端端口转发，只转发不占 GPU）：
   ```bash
   ssh -N -L 7860:localhost:7860 autodl     # ~/.ssh/config 里已配好别名 autodl
   # 浏览器打开 http://localhost:7860
   ```

### 开发机模式（共用一个支持 `.venv-verify` 的轻量环境）
- 纯 CPU 的数据治理管道**可本地验证**，不必挂卡/开云：
  ```bash
  cd D:\claude\llm-platform
  .venv-verify\Scripts\python -c "from llm_platform.data_pipeline import run_pipeline; ..."
  ```
  > `.venv-verify` 只装了 pandas/numpy（几十 MB）；Windows 控制台打印中文可能乱码，`set PYTHONIOENCODING=utf-8` 可避免。
- **推理/训练必须 GPU**（聊天、模型加载），只在云端跑。

### 切换模型
`config.py`：
```python
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"   # 可换同系列 1.5B/14B
QUANTIZATION = "none"                     # "none" | "8bit"（需装 bitsandbytes）
```

## 数据治理用法

进入「数据治理」Tab：
1. 选领域（医疗/法律/金融/教育）。
2. 数据源二选一：**上传文件**（.json/.jsonl/.csv/.txt）或 **粘贴纯文本**（每段以空行分隔，医疗/法律会自动生成问答对）。
3. 设参数（最小/最大长度、去重、质量阈值）→ 点「运行治理」。
4. 看三表：**统计**（总数/保留/丢弃 + 每阶段处置 + 丢弃原因分布）、**样本明细**、**输出路径**；可下载 `sharegpt.jsonl`。

命令行等价：
```python
from llm_platform.data_pipeline import run_pipeline
res = run_pipeline("医疗", file_paths=["病历.jsonl"], texts=["粘贴的纯文本…"],
                   min_len=10, max_len=2000, dedup=True, score_cutoff=0.4)
print(res.kept, res.drop_reasons, res.output_files)   # 落盘 data/医疗_sharegpt.jsonl
```

## 领域预设如何扩展

- **改规则**：直接编辑 `resources/<domain>/*.json`（脱敏词表、小节名、单位、质控阈值、QC 规则、文书类型、层级标记…），无需改代码 → `run_pipeline` 即生效。
- **加阶段**：在 `stages_generic.py` 加一个 `Stage` 子类，注册进 `domain_presets/__init__.py` 的 `STAGE_REGISTRY`，再在 `preset.json` 的 `stages` 里加 `{"kind":"名字"}`。
- **新领域**：建 `resources/<slug>/` + `preset.json` + 资源表；`domain.py` 加 slug 映射。

## 常见问题

- **`CUDA 不可用`**：在无 GPU 机器上跑。聊天/训练需 AutoDL GPU 实例；数据治理纯 CPU 无需。
- **聊天无卡也用不了**：应用在无卡时也能启动（预热失败被捕获），仅对话 Tab 需挂卡才可用。
- **无卡能看到数据治理但点对话报错**：正常，属预期。
- **首次权重下载慢**：AutoDL 开「学术加速」。
- **版本冲突**：AutoDL 镜像 torch 较旧时，去掉 `requirements.txt` 里 `transformers` 的版本号再 `pip install -U transformers gradio accelerate`。
- **本地改代码要上云**：`./deploy.sh` 一键推码 + 重启；`./deploy.sh logs` 看日志。

## 路线图

| Sprint | 内容 | 状态 |
|---|---|---|
| 0 | 工作台 + Qwen 流式对话 | ✅ 完成 |
| 1 | 数据治理 + 领域预设（医疗/法律深、金融/教育薄）+ 纯文本输入 | ✅ 完成 |
| 3 | LoRA 微调 + 自动保存权重 | ⏳ 占位 |
| 4 | 权重复用对话 + 多轮记忆加强 | ⏳ 占位 |
| 5 | 多维度评测 + 跨领域对比 | ⏳ 占位 |
