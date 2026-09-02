# 数据处理模块测试（unittest，零安装）

覆盖 `docs/DATASETS.md` 列出的全部数据源（每个 reader 分支 + 各领域严格/宽松预设的 keep|drop）。在 `D:\claude\llm-platform\.venv-verify`（仅 pandas/numpy）下即可运行。

## 运行

```bash
PYTHONIOENCODING=utf-8 .venv-verify/Scripts/python -m unittest discover -s tests -t . -v
# 单文件
PYTHONIOENCODING=utf-8 .venv-verify/Scripts/python -m unittest tests.test_pipeline -v
```

`tests/_helpers.py` 会把 `llm_platform.data_pipeline.io.DATA_DIR` 指向每个测试的临时目录（**Hermetic**），运行不污染 `data/`。

## 文件

- `test_readers.py` —— `read_inputs` 归一化（结构化断言，无盘写）。
- `test_pipeline.py` —— `run_pipeline` 全链路（领域→预设→keep/drop→落盘 Alpaca）。
- `_helpers.py` —— `reader()`、`PipelineTestCase`（临时 DATA_DIR + `read_output`）。
- `fixtures/` —— 测试输入，**提交进 git**，离线确定性。
- `build_fixtures.py` —— 一次性重建 fixtures（联网克隆→截取→重排；需先 `git clone` 各源到 `%LOCALAPPDATA%\Temp\llm_fixtures_scratch`）。测试运行不依赖它。

## fixture 来源（真实性说明）

| 来源 | fixture | 说明 |
|---|---|---|
| 真实 CMB-Exam | `cmb_exam_medical.jsonl` | 用 `CMB-test-choice-question-merge.json` 与 `CMB-test-choice-answer.json` join |
| 真实 CMB-Clin | `cmb_clin_medical.jsonl` | `QA_pairs`（真实字段为 `answer` 而非 `solution`） |
| 真实 Toyhom | `toyhom_medical.csv` | GBK，`department/title/ask/answer` |
| 真实 LawBench | `lawbench_qa_legal.jsonl` | `zero_shot/2-1`（question/answer） |
| 真实 LawCrime | `raw_legal_judgment.txt` | `corpus_lawsuit/24` 刑事判决书（>默认 max_len，测试放大） |
| 真实 CMMLU | `cmmlu_education.csv`、`mmlu_education.csv` | 大写列+前导序号；MMLU 用真实 CMMLU 行按小写列重排 |
| 重排真实内容 | `medqa`、`fineval_*`、`huatuo`、`disc_law`、`lawbench_summary`、`raw_medical` | 真实 CMB/Toyhom/LawCrime 内容，按各自 schema 重排（MedQA/FinEval 数据在 Drive/.rar 不可下；DISC-Law/Huatuo 仅 HF 托管、本机被阻断） |
| 构造 | `raw_legal_contract`、`finance_report_cn`、`*_cn_bad`、`fingpt_*` | 无真实来源（合同/研报无语料；坏样本专测严格预设的丢弃分支） |

## 过程中的生产代码改动

`llm_platform/data_pipeline/readers.py` 的 `_clin_to_items`：
- 原：只读 `QA_pairs[].solution`。
- 现：`solution or answer`。**真实 CMB-Clin 数据用的是 `answer` 键**，按原逻辑全部 `QA_pairs 均无法解析`（`total=0`），与 DATASETS.md 及项目"复数键兼容"目标不符。此改动让真实 CMB-Clin 可被处理并纳入测试。**仅供审查，若不需要可回退**（回退后 `test_cmb_clin_medical_qa_kept` / `test_cmb_clin_medical_cn_dropped` 会失败）。
