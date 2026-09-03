# 数据处理模块测试（unittest，零安装）

覆盖 `docs/DATASETS.md` 列出的全部数据源（每个 reader 分支 + 各领域严格/宽松预设的 keep|drop）。在 `D:\claude\llm-platform\.venv-verify`（仅 pandas/numpy）下即可本地运行。

## 运行方式

### 本地离线（fixtures 已提交进 git）
```bash
PYTHONIOENCODING=utf-8 .venv-verify/Scripts/python -m unittest discover -s tests -t . -v
# 单文件
PYTHONIOENCODING=utf-8 .venv-verify/Scripts/python -m unittest tests.test_pipeline -v
```

### 云端流水线（下载真实数据 → 重建 fixtures → 测试 → 可视化，推荐）
```bash
git add -A && git commit -m "..." && git push origin main
./deploy.sh datatest            # 云端一键：下载→build_fixtures→测试→报告
./deploy.sh report              # 云端起静态服务+端口转发，浏览器打开报告
# 浏览器访问 http://localhost:8899/report.html
```
流水线 = `tests/cloud_run.sh`：`download_datasets.py --all`（幂等，已下载跳过）
→ `build_fixtures.py`（从真实源截取）→ `build_fixtures.py --check`（关键 fixture 齐全性守卫）
→ `run_and_report.py`（自包含 HTML + JSON 报告）。**下载的原始数据落在
`tests/fixtures/_downloads/`，不入库**（见 .gitignore）；fixtures 小样本与脚本入库，
因此下载失败时仍可用 git 内 fixtures 离线路子集。

## 文件

- `test_readers.py` —— `read_inputs` 归一化（结构化断言，无盘写）。
- `test_pipeline.py` —— `run_pipeline` 全链路（领域→预设→keep/drop→落盘 Alpaca）。
- `_helpers.py` —— `reader()`、`PipelineTestCase`（临时 DATA_DIR + `read_output`）。
- `download_datasets.py` —— **数据集下载器**（零第三方依赖）：GitHub 源 `git clone --depth=1`（大仓库稀疏检出）、
  HuggingFace 源走 HF API resolve 直下（支持 `HF_ENDPOINT` 镜像）、MedQA Drive 走可选 `gdown`；
  幂等（`.done.json`）/重试退避/进度条/`--source` 选择性/`--force`/`--dry-run`/`--limit-files`/大小校验；
  汇总写 `fixtures/_downloads/manifest.json`。`python tests/download_datasets.py --list` 查看全部源。
- `build_fixtures.py` —— 从 `_downloads/` 截取小样本生成 `fixtures/`（离线冻结；`--check` 校验关键产物）。
- `run_and_report.py` —— 跑测试生成 **自包含 HTML 报告**（汇总卡片/通过率/按类条形/用例明细/失败 traceback 折叠）+ JSON。
- `cloud_run.sh` —— 云端一键流水线（见上）。
- `fixtures/` —— 测试输入，**提交进 git**，离线确定性；`fixtures/_downloads/` 为下载缓存，**不入库**。

## fixture 来源（真实性说明）

builder 采用**真实优先 + 兜底**策略：云端 `_downloads/` 有真实数据时用真实，无时走重排/构造兜底（保本地离线可跑）。
断言 accordingly 改为「reader 加的稳定前缀（如 `答案：`/`题：`/`科室：`）+ 结构」；数据内容特异性断言已移除，以兼容真实/兜底两种产出。

| 来源 | fixture | 真实优先来源 | 兜底 |
|---|---|---|---|
| CMB | `cmb_exam/clin_medical.jsonl`、`raw_medical.txt` | `_downloads/cmb/`（自动解压 CMB.zip） | — |
| Toyhom | `toyhom_medical.csv` | `_downloads/toyhom/`（GBK） | — |
| LawBench | `lawbench_qa_legal.jsonl` | `_downloads/lawbench/data/zero_shot/2-1.json` | — |
| LawCrime | `raw_legal_judgment.txt` | `_downloads/lawcrime/corpus_lawsuit/24.txt` | — |
| CMMLU | `cmmlu_education.csv` | `_downloads/cmmlu/data/dev/agronomy.csv` | — |
| MedQA | `medqa_medical.jsonl` | `_downloads/medqa_drive/`（需 gdown） | CMB-Exam 重排 |
| Huatuo | `huatuo_medical.jsonl` | `_downloads/huatuo/` parquet（需 pyarrow） | Toyhom 重排 |
| DISC-Law | `disc_law_legal.jsonl` | `_downloads/disc_law/` parquet（需 pyarrow） | LawBench 重排 |
| FinEval | `fineval_mcq/qa_finance.jsonl` | `_downloads/fineval/data-v2/` jsonl | CMB/Toyhom 重排 |
| fingpt | `fingpt_finance.jsonl` | `_downloads/fingpt/` parquet（挑无数值+单位行以测 finance_cn 丢弃，需 pyarrow） | 构造 |
| MMLU | `mmlu_education.csv` | `_downloads/mmlu/data/` csv | CMMLU 行重排 |
| EduChat | `educhat_education.jsonl` | `_downloads/educhat/`（挑无选项开放问答以测 education_cn 丢弃） | 构造 |
| 构造 | `raw_legal_contract`、`finance_report_cn`、`*_cn_bad` | — | 始终构造（无真实来源/专测丢弃分支） |

## 过程中的生产代码改动

`llm_platform/data_pipeline/readers.py` 的 `_clin_to_items`：
- 原：只读 `QA_pairs[].solution`。
- 现：`solution or answer`。**真实 CMB-Clin 数据用的是 `answer` 键**，按原逻辑全部 `QA_pairs 均无法解析`（`total=0`），与 DATASETS.md 及项目"复数键兼容"目标不符。此改动让真实 CMB-Clin 可被处理并纳入测试。**仅供审查，若不需要可回退**（回退后 `test_cmb_clin_medical_qa_kept` / `test_cmb_clin_medical_cn_dropped` 会失败）。
