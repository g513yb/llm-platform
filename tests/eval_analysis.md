# 模型评估报告（第二轮）

## 评估范围
26 个 pipeline 测试用例的实际 Alpaca 输出，由 GLM-5.2 逐条语义质量评估。

## 评估结果总览

| 指标 | 值 |
|------|-----|
| 总用例数 | 26 |
| 通过 | 26 |
| 失败 | 0 |
| 质量=high | 18 |
| 质量=moderate | 2 |
| 质量=n/a（drop/bad 用例） | 6 |

## 第一轮发现的问题及修复状态

### 已修复（6/6）

| # | 问题 | 修复方案 | 验证结果 |
|---|------|---------|---------|
| 1 | MMLU CSV 列名 `mr["A"]`→`mr["a"]`，answer 数字→字母 | `build_fixtures.py` 列名修复 + answer 转换 | MMLU 1→96 行真实英文题 ✅ |
| 2 | FinEval 兜底用医学题冒充金融 | 领域内构造（市盈率/GDP/CAPM/巴塞尔III 等 10 MCQ + 5 QA） | 金融概念准确 ✅ |
| 3 | MedQA 兜底用虚假 src:us 标签 | 改为 src=cmb_exam 诚实标注 | 标注真实 ✅ |
| 4 | DISC-Law 兜底用 LawBench 纠错冒充 | 领域内构造（民法典/劳动法/公司法咨询 5 条） | 法律内容准确 ✅ |
| 5 | LawBench 丢掉 instruction 字段 | 保留 instruction，fixture 改为完整 Alpaca | 纠错任务完整 ✅ |
| 6 | 答案冒号全角/半角不一致 | readers.py + options.json 统一半角 `答案:X` | 全部半角 ✅ |

### 未修复（已知限制）

| # | 问题 | 原因 | 影响 |
|---|------|------|------|
| 1 | FinEval 用领域内构造而非原始数据 | .rar 无法解压（无 unrar 工具） | 金融概念准确但非原始考题 |
| 2 | DISC-Law 用领域内构造而非原始数据 | 下载失败（网络不可达） | 法律内容准确但非原始数据 |
| 3 | MedQA 用 CMB-Exam 标注而非原始数据 | Google Drive 不可达 | 数据真实但来源标注为 cmb_exam |
| 4 | Toyhom 源数据翻译噪声 | 原始数据质量问题 | 答案相关但有错别字 |

## 逐案评估

### 医疗领域（8 用例）

| 用例 | kept/dropped | 质量 | 评估 |
|------|-------------|------|------|
| cmb_exam_medical_qa | 100/0 | high | 真实医师考试单选题，格式统一 `答案:X` |
| cmb_clin_medical_qa | 74/0 | high | 真实临床病例分析，诊断/依据/鉴别诊断结构完整 |
| toyhom_medical_qa | 100/0 | moderate | 真实医患问答，源数据有翻译噪声 |
| medqa_medical_qa | 100/0 | high | CMB-Exam 医学题，src 标注诚实 |
| huatuo_medical_qa | 100/0 | high | Huatuo-26M-Lite 真实问答，回答连贯 |
| raw_medical_cn | 1/0 | high | 病历结构化提取正确 |
| cmb_clin_medical_cn | 4/70 | high | 严格预设正确过滤缺诊断/主诉的病例 |
| cmb_clin_bad_cn | 0/1 | n/a | 坏数据正确被拒 |

### 法律领域（7 用例）

| 用例 | kept/dropped | 质量 | 评估 |
|------|-------------|------|------|
| lawbench_qa | 100/0 | high | 法律文书纠错，修正精准（上诉→上述、苯院→本院等） |
| lawbench_cn | 14/86 | high | 严格预设过滤低分，保留14条有法律结构的纠错 |
| disc_law_qa | 5/0 | high | 领域内构造问答，民法典/劳动法/公司法内容准确 |
| lawbench_summary_qa | 1/0 | high | 法条核心要义概括准确 |
| raw_legal_judgment_cn | 1/0 | high | 判决书关键信息提取正确 |
| raw_legal_judgment_bad_cn | 0/1 | n/a | 坏判决书正确被拒 |
| raw_legal_contract_cn | 1/0 | high | 合同关键条款提取正确 |

### 金融领域（6 用例）

| 用例 | kept/dropped | 质量 | 评估 |
|------|-------------|------|------|
| fineval_mcq_qa | 10/0 | high | 领域内构造选择题，含答案+解析，概念准确 |
| fineval_qa_qa | 5/0 | high | 领域内构造问答，货币政策/流动性陷阱/费雪效应等 |
| fingpt_qa | 100/0 | high | 真实金融情感分类，标签与语义一致 |
| fingpt_cn | 0/100 | n/a | 情感数据无数值指标，严格预设正确过滤 |
| fingpt_bad_cn | 0/1 | n/a | 坏数据正确被拒 |
| finance_report_cn | 1/0 | high | 研报关键指标提取正确 |

### 教育领域（5 用例）

| 用例 | kept/dropped | 质量 | 评估 |
|------|-------------|------|------|
| mmlu_cn | 96/4 | high | 真实MMLU英文数学题，格式统一 `答案:X`（半角冒号已修复） |
| cmmlu_cn | 4/0 | high | 真实CMMLU中文农业选择题，格式统一 |
| educhat_qa | 1/0 | moderate | 光合作用解释正确但偏简短 |
| educhat_cn | 0/1 | n/a | 问答无选项，严格预设正确过滤 |
| educhat_bad_cn | 0/1 | n/a | 坏数据正确被拒 |

## 结论

第一轮发现的 6 个问题全部修复验证通过。26 个用例全部 PASS，18 个 high quality。剩余限制（FinEval/DISC-Law/MedQA 用领域内构造替代原始数据）为网络/工具不可达导致，构造内容经过语义验证准确可靠。
