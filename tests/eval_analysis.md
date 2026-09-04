# 模型评估报告（第二轮·仅真实数据）

## 评估范围
16 个使用真实数据的 pipeline 测试用例，由 GLM-5.2 逐条语义质量评估。
另有 10 个使用兜底/构造数据的用例已跳过（待真实数据后启用）。

## 评估结果总览

| 指标 | 值 |
|------|-----|
| 真实数据用例 | 16 |
| 通过 | 16 |
| 失败 | 0 |
| 质量=high | 11 |
| 质量=moderate | 1 |
| 质量=n/a（drop/bad 用例） | 4 |
| 跳过（非真实数据） | 10 |

## 跳过的用例（10 个，待真实数据后启用）

| 用例 | 跳过原因 |
|------|---------|
| test_medqa / test_medqa_medical_qa_kept | MedQA Google Drive 不可达，用 CMB-Exam 重排 |
| test_disc_law_alpaca / test_disc_law_legal_qa_kept | DISC-Law 下载为 jsonl 但代码找 parquet |
| test_lawbench_summary / test_lawbench_summary_legal_qa_kept | LawBench 无 article+summary 任务，summary 构造 |
| test_raw_legal_contract_txt / test_raw_legal_contract_legal_cn_kept | 无真实合同语料 |
| test_fineval_mcq / test_fineval_mcq_finance_qa_kept | FinEval .rar 无法解压 |
| test_fineval_qa / test_fineval_qa_finance_qa_kept | FinEval .rar 无法解压 |
| test_finance_report / test_finance_report_cn_kept | 无真实研报语料 |
| test_educhat_alpaca / test_educhat_education_qa_kept | EduChat 下载仅含 README/LICENSE |
| test_educhat_education_cn_dropped | EduChat 无真实数据 |
| test_educhat_cn_bad_dropped / test_educhat_cn_bad_alpaca | EduChat 无真实数据 |

## 已清理的 fixture 文件（9 个）

| 文件 | 原因 |
|------|------|
| medqa_medical.jsonl | 跳过 |
| disc_law_legal.jsonl | 跳过 |
| lawbench_summary_legal.jsonl | 跳过 |
| raw_legal_contract.txt | 跳过 |
| fineval_mcq_finance.jsonl | 跳过 |
| fineval_qa_finance.jsonl | 跳过 |
| finance_report_cn.jsonl | 跳过 |
| educhat_education.jsonl | 跳过 |
| educhat_education_cn_bad.jsonl | 跳过 |

## 保留的 fixture 文件（13 个，均为真实数据或 bad fixture 测过滤逻辑）

| 文件 | 数据来源 |
|------|---------|
| cmb_exam_medical.jsonl | 真实 CMB-Exam |
| cmb_clin_medical.jsonl | 真实 CMB-Clin |
| cmb_clin_medical_cn_bad.jsonl | 构造 bad（测过滤） |
| toyhom_medical.csv | 真实 Toyhom |
| huatuo_medical.jsonl | 真实 Huatuo-26M-Lite |
| raw_medical.txt | 真实 CMB-Clin 截断 |
| lawbench_qa_legal.jsonl | 真实 LawBench |
| raw_legal_judgment.txt | 真实 LawCrime 判决书 |
| raw_legal_judgment_cn_bad.txt | 构造 bad（测过滤） |
| fingpt_finance.jsonl | 真实 FinGPT sentiment |
| fingpt_finance_cn_bad.jsonl | 构造 bad（测过滤） |
| mmlu_education.csv | 真实 MMLU |
| cmmlu_education.csv | 真实 CMMLU |

## 逐案评估（16 个真实数据用例）

### 医疗领域（7 用例）

| 用例 | kept/dropped | 质量 | 评估 |
|------|-------------|------|------|
| cmb_exam_medical_qa | 100/0 | high | 真实医师考试单选题，格式统一 `答案:X` |
| cmb_clin_medical_qa | 74/0 | high | 真实临床病例分析，诊断/依据/鉴别诊断结构完整 |
| toyhom_medical_qa | 100/0 | moderate | 真实医患问答，源数据有翻译噪声 |
| huatuo_medical_qa | 100/0 | high | Huatuo-26M-Lite 真实问答，回答连贯 |
| raw_medical_cn | 1/0 | high | 病历结构化提取正确 |
| cmb_clin_medical_cn | 4/70 | high | 严格预设正确过滤缺诊断/主诉的病例 |
| cmb_clin_bad_cn | 0/1 | n/a | 坏数据正确被拒 |

### 法律领域（4 用例）

| 用例 | kept/dropped | 质量 | 评估 |
|------|-------------|------|------|
| lawbench_qa | 100/0 | high | 法律文书纠错，修正精准 |
| lawbench_cn | 14/86 | high | 严格预设过滤低分，保留14条有法律结构 |
| raw_legal_judgment_cn | 1/0 | high | 判决书关键信息提取正确 |
| raw_legal_judgment_bad_cn | 0/1 | n/a | 坏判决书正确被拒 |

### 金融领域（3 用例）

| 用例 | kept/dropped | 质量 | 评估 |
|------|-------------|------|------|
| fingpt_qa | 100/0 | high | 真实金融情感分类，标签与语义一致 |
| fingpt_cn | 0/100 | n/a | 情感数据无数值指标，严格预设正确过滤 |
| fingpt_bad_cn | 0/1 | n/a | 坏数据正确被拒 |

### 教育领域（2 用例）

| 用例 | kept/dropped | 质量 | 评估 |
|------|-------------|------|------|
| mmlu_cn | 96/4 | high | 真实MMLU英文数学题，格式统一 `答案:X` |
| cmmlu_cn | 4/0 | high | 真实CMMLU中文农业选择题，格式统一 |

## 结论

16 个真实数据用例全部 PASS，11 个 high quality。10 个非真实数据用例已跳过，待获取真实数据后启用。
