# 模型评估报告（第三轮·仅真实数据）

## 评估范围
17 个使用真实数据的 pipeline 测试用例，由 GLM-5.2 逐条语义质量评估。
另有 9 个使用兜底/构造数据的用例已跳过（待真实数据后启用）。

## 评估结果总览

| 指标 | 值 |
|------|-----|
| 真实数据用例 | 17 |
| 通过 | 17 |
| 失败 | 0 |
| 质量=high | 13 |
| 质量=moderate | 0 |
| 质量=n/a（drop/bad 用例） | 4 |
| 跳过（非真实数据） | 9 |

## 跳过的用例（9 个，待真实数据后启用）

| 用例 | 跳过原因 |
|------|---------|
| test_medqa / test_medqa_medical_qa_kept | MedQA Google Drive 不可达，用 CMB-Exam 重排 |
| test_lawbench_summary / test_lawbench_summary_legal_qa_kept | LawBench 无 article+summary 任务，summary 构造 |
| test_raw_legal_contract_txt / test_raw_legal_contract_legal_cn_kept | 无真实合同语料 |
| test_fineval_mcq / test_fineval_mcq_finance_qa_kept | FinEval .rar 无法解压 |
| test_fineval_qa / test_fineval_qa_finance_qa_kept | FinEval .rar 无法解压 |
| test_finance_report / test_finance_report_cn_kept | 无真实研报语料 |
| test_educhat_alpaca / test_educhat_education_qa_kept | EduChat 下载仅含 README/LICENSE |
| test_educhat_education_cn_dropped | EduChat 无真实数据 |
| test_educhat_cn_bad_dropped / test_educhat_cn_bad_alpaca | EduChat 无真实数据 |

## 保留的 fixture 文件（14 个，均为真实数据或 bad fixture 测过滤逻辑）

| 文件 | 数据来源 |
|------|---------|
| cmb_exam_medical.jsonl | 真实 CMB-Exam |
| cmb_clin_medical.jsonl | 真实 CMB-Clin |
| cmb_clin_medical_cn_bad.jsonl | 构造 bad（测过滤） |
| toyhom_medical.csv | 真实 Toyhom（跨科室轮询23科室） |
| huatuo_medical.jsonl | 真实 Huatuo-26M-Lite |
| raw_medical.txt | 真实 CMB-Clin 截断 |
| lawbench_qa_legal.jsonl | 真实 LawBench（多子任务合并） |
| disc_law_legal.jsonl | 真实 DISC-Law-SFT（552MB jsonl） |
| raw_legal_judgment.txt | 真实 LawCrime 判决书 |
| raw_legal_judgment_cn_bad.txt | 构造 bad（测过滤） |
| fingpt_finance.jsonl | 真实 FinGPT sentiment |
| fingpt_finance_cn_bad.jsonl | 构造 bad（测过滤） |
| mmlu_education.csv | 真实 MMLU（多学科合并） |
| cmmlu_education.csv | 真实 CMMLU（多学科合并） |

## 逐案评估（17 个真实数据用例）

### 医疗领域（7 用例）

| 用例 | kept/dropped | 质量 | 评估 |
|------|-------------|------|------|
| cmb_exam_medical_qa | 100/0 | high | 真实医师考试单选题，格式统一 `答案:X` |
| cmb_clin_medical_qa | 74/0 | high | 真实临床病例分析，诊断/依据/鉴别诊断结构完整 |
| toyhom_medical_qa | 100/0 | high | 真实医患问答（跨科室轮询23科室），已修复明显翻译错误 |
| huatuo_medical_qa | 100/0 | high | Huatuo-26M-Lite 真实问答，回答连贯 |
| raw_medical_cn | 1/0 | high | 病历结构化提取正确 |
| cmb_clin_medical_cn | 4/70 | high | 严格预设正确过滤缺诊断/主诉的病例 |
| cmb_clin_bad_cn | 0/1 | n/a | 坏数据正确被拒 |

### 法律领域（5 用例）

| 用例 | kept/dropped | 质量 | 评估 |
|------|-------------|------|------|
| lawbench_qa | 100/0 | high | 法律文书纠错，修正精准 |
| lawbench_cn | 98/2 | high | 严格预设过滤低分，保留有法律文书结构的纠错 |
| disc_law_qa | 100/0 | high | 真实DISC-Law-SFT jsonl（552MB），法律咨询问答内容准确 |
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
| mmlu_cn | 96/4 | high | 真实MMLU多学科英文题，格式统一 `答案:X` |
| cmmlu_cn | 100/0 | high | 真实CMMLU多学科中文选择题，格式统一 |

## 本轮改进

1. **Toyhom 跨科室轮询**：从单科室100条改为跨23科室轮询100条，样本多样性大幅提升
2. **Toyhom 翻译噪声修复**：修复明显翻译错误 `心里因素→心理因素`、`股份骨折→骨盆骨折`
3. **DISC-Law 重新启用**：路径修复 + 读 .jsonl 格式，552MB 真实数据启用

## 结论

17 个真实数据用例全部 PASS，13 个 high quality，0 个 moderate。9 个非真实数据用例已跳过，待获取真实数据后启用。
