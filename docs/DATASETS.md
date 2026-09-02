# 支持的数据集与使用说明

llm-platform 的「数据处理」可直接读取阿里/清华等来源的**医疗、法律**公开数据集。本文给出各数据的**获取方式、字段、推荐预设、上传前处理**。上传后统一在「数据处理」Tab 选**领域 + 预设**即可清洗落盘。

> 说明：以下字段/加载方式按各仓库 README 与实测样本核对；因网络限制暂无法在线抓取部分卡片原文，加载名称以各仓库为准（均给出链接）。

## 通用：如何把数据喂给 llm-platform

- **HuggingFace 数据集**（CMB / DISC-Law-SFT / Huatuo-26M）：用 `datasets` 加载后导出本地文件再上传：
  ```python
  from datasets import load_dataset
  ds = load_dataset("FreedomIntelligence/Huatuo-26M", split="train").select(range(10000))  # 若太大先抽样
  ds.to_json("huatuo.jsonl")   # 或 ds.to_csv("huatuo.csv")
  # 把 huatuo.jsonl 上传到「数据处理」即可
  ```
- **GitHub 仓库**：`git clone <url>` 后，直接上传仓库里的 `.jsonl`/`.csv`；raw 文书 `.txt` 也支持（法律走规则抽取合成问答对）。
- 上传后在「数据处理」Tab：选领域（医疗/法律/金融）→ 选**预设** → 选文件 → 运行治理 → 落盘 **Alpaca `{instruction,input,output}`**（训练用；`config.OUTPUT_FORMAT` 可切回 `sharegpt`）。

---

## 医疗

### CMB（CMB-Exam / CMB-Clin）
- 仓库：https://github.com/FreedomIntelligence/CMB （HF 镜像 `FreedomIntelligence/CMB`）
- 性质：医学考试基准 + 临床病例。
- 获取：`git clone https://github.com/FreedomIntelligence/CMB.git && cd CMB && unzip data/CMB.zip -d data/`；或 `load_dataset("FreedomIntelligence/CMB", "exam")` / `("clin")`。
- 字段：
  - CMB-Exam：`exam_type / exam_class / exam_subject / question / answer(字母) / question_type / option{A..E}`
  - CMB-Clin：`id / title / description(病历) / QA_pairs[{question, solution}]`
- 预设：选择题→**medical_qa（宽松）**；Clin 病例→**medical_cn（严格）** 或 medical_qa。

### Toyhom 中文医患对话
- 仓库：https://github.com/Toyhom/Chinese-medical-dialogue-data
- 性质：医患问答，6 科室，约 79 万条。
- 获取：`git clone`；数据在 `Data_数据/<科室>/<科室>x-y.csv`（GBK 编码）。README 也提供 Alpaca 版。
- 字段：`department / title / ask / answer`（CSV，GBK 自动识别）。
- 预设：**medical_qa（宽松）**。

### MedQA
- 仓库：https://github.com/jind11/MedQA
- 性质：USMLE 型医学单选题（已按仓库 README 原文核对）。
- 获取：数据经仓库 README 的 **Google Drive 链接**下载；含 US/中国大陆/台湾三个来源，均 **jsonl**（每行一个 dict），并提供 4 选项 / 5 选项版与官方 train/dev/test 划分 → 得到 `*_qbank.jsonl` 等，直接上传 jsonl。
- 字段：`question / options{A..E} / answer_idx(字母) / answer(解析) / meta_info`
- 预设：**medical_qa（宽松）**。

### Huatuo-26M
- HF 数据集：https://huggingface.co/datasets/FreedomIntelligence/Huatuo-26M
- 性质：大型中文医患问答，约 2600 万条。
- 获取：`load_dataset("FreedomIntelligence/Huatuo-26M", split="train")`；**数量极大，务必先抽样/选 source 子集**再导出。
- 字段：`question / response`（另有 `answer_type / source`）。
- 预设：**medical_qa（宽松）**。

---

## 法律

### DISC-Law-SFT
- HF 数据集：https://huggingface.co/datasets/ShengbinYue/DISC-Law-SFT
- 性质：中文法律指令 SFT 数据集（DISC-LawLLM）。
- 获取：`load_dataset("ShengbinYue/DISC-Law-SFT")` → 导出 jsonl/csv。
- 字段：`instruction / input / output`（Alpaca，llm-platform 原生支持）。
- 预设：**legal_qa（宽松）**（默认严格 legal_cn 会因无文书结构而丢弃）。

### LawBench
- 仓库：**https://github.com/open-compass/LawBench**（原给出的 CSH-LawBench/LawBench 已 404；相关镜像 [open-mmlab-12/LawBench](https://github.com/open-mmlab-12/LawBench)）
- 性质：法律基准（OpenCompass 集成，20 任务 × 500 例），含法条检索 / 判决预测 / 法律问答 / 法条摘要等。
- 获取：`git clone https://github.com/open-compass/LawBench`；`data/` 下每任务一个 jsonl。
- 字段：各任务不一；本平台支持 **问答(`question/answer`)** 与 **摘要(`article/summary`)** 形态；**法条检索 / 判决预测为评测负载，留待后续「多维度评测」Sprint**。
- 预设：**legal_qa（宽松）**。

### Chinese-Law-Doc（中文法律文书语料）
- 仓库：**https://github.com/liuhuanyong/LawCrimeMining**（裁判文书 ≈10.8 万 + 犯罪案例 ≈6.3 万，raw 文本；原给出的 `liuhuanyong/Chinese-Law-Doc` 已 404）
- 另有：**https://github.com/liuhuanyong/CrimeKgAssitant**（犯罪知识图谱 856 类 + 约 20 万法务问答）
- 性质：中文裁判文书/犯罪案例 **raw 文本**。
- 获取：`git clone`；按文件夹含 `.txt` 文书。
- 字段：纯文本；llm-platform 的 `txt_generator` 自动按文书类型合成问答对：**法规→抽取第X条**、**判决书→案号/当事人/本院认为/判决**、**合同→甲方/乙方/标的/关键条款**。
- 预设：合成后在「法律」预设选 **legal_cn（文书严格）** 或 legal_qa。

---

## 金融

### FinEval
- 仓库：https://github.com/SUFE-AIFLM-Lab/FinEval
- 性质：金融知识基准（约 2.6 万题）：**学术类选择题**（MCQ 4661 题）+ **行业类开放问答**（1434 题）等。
- 获取：`git clone https://github.com/SUFE-AIFLM-Lab/FinEval`；数据在 `data-v2/`（JSONL，每行一个 dict）。
- 字段：选择题 `question / options{A..D} / answer(字母) [+ Explanation]`；开放问答 `question / answer`。
- 预设：**finance_qa（宽松）**。

### fingpt-sentiment-train
- HF 数据集：https://huggingface.co/datasets/FinGPT/fingpt-sentiment-train
- 性质：金融情感倾向分类（一段金融文本 → 正/负/中性标签）。
- 获取：`load_dataset("FinGPT/fingpt-sentiment-train")` → 导出 jsonl/csv。
- 字段：`input（金融文本）/ output（情感标签）`。
- 预设：**finance_qa（宽松）** —— 纯文本无数字/单位时 `finance_cn` 会因"必需数值指标"丢弃，故用宽松。

### BloombergGPT
- 说明：**无官方公开数据集**（模型与 FinPile 未开源，仅论文 [arXiv:2303.17564](https://arxiv.org/abs/2303.17564)）。本平台不提供摄入入口；如需金融语料请使用上面的 FinEval / fingpt。

---

## 教育

### MMLU（hendrycks/test，即 MMLU）
- 仓库：https://github.com/hendrycks/test
- 性质：通用多选题基准（57 科目），CSV `question,A,B,C,D,answer`（答案=字母）。
- 获取：`git clone # https://github.com/hendrycks/test` → `data/{dev,val,test}/*.csv`。
- 字段：`question / A..D / answer(字母)`。
- 预设：**education_cn**（选择题；读入时自动把选项拼进 user，答案`答案：X`）。

### CMMLU
- 仓库：https://github.com/haonan-li/CMMLU
- 性质：中文多选题基准（约 67 科目），CSV `Question,A,B,C,D,Answer`（大写 + 前导序号列，答案=字母）。
- 获取：`git clone https://github.com/haonan-li/CMMLU` → `data/{dev,test}/*.csv`。
- 字段：`Question / A..D / Answer(字母)`。
- 预设：**education_cn**（选择题）。

### EduChat
- 仓库：**https://github.com/ECNU-ICALK/EduChat**（华东师大 ICALK 教育对话大模型；原给出的 `iecsql/EduChat` 已 404，早期为 `icalk-nlp/EduChat`）。
- 性质：中文教育对话/指令数据（出题、批改、心理疏导、辅导、高考咨询等，多为 Alpaca `instruction/input/output`）。
- 获取：见仓库；其教育 SFT 多为指令/问答对（语料量大，仓库以样例/外部为准）。
- 字段：`instruction / input / output`（Alpaca）。
- 预设：**education_qa**（宽松）——非选择题的自由问答在 `education_cn`（"选项+答案"校验）下会被丢弃，故用宽松。

## 预设选择对照

| 数据 | 领域 | 推荐预设 |
|---|---|---|
| CMB-Exam（选择题）| 医疗 | medical_qa |
| CMB-Clin（病例）| 医疗 | medical_cn（或 medical_qa）|
| Toyhom / MedQA / Huatuo-26M | 医疗 | medical_qa |
| DISC-Law-SFT / LawBench(问答·摘要) | 法律 | legal_qa |
| Chinese-Law-Doc（raw 文书）| 法律 | legal_cn（合成后）|
| FinEval / fingpt-sentiment / 金融问答 | 金融 | finance_qa |
| 金融数值研报（含 % / 亿元）| 金融 | finance_cn |
| MMLU / CMMLU（多选题）| 教育 | education_cn |
| EduChat / 教育问答 | 教育 | education_qa |

> 医疗/法律/金融/教育各有两个预设：`medical_cn`/`medical_qa`、`legal_cn`/`legal_qa`、`finance_cn`/`finance_qa`、`education_cn`/`education_qa`；前者严格（要求结构/文书/数值指标/选项答案），后者宽松（仅清洗/术语/质量分），考试问答类选宽松，病历/文书/数值/选择类选严格。

## ⚠️ 注意（账号/地址可能变动）
- **LawBench**（`github.com/CSH-LawBench/LawBench`）与 **Chinese-Law-Doc**（`github.com/liuhuanyong/Chinese-Law-Doc`）在本文核对时**返回 404**（可能已迁移/改名/私有化；同是 GitHub 的 MedQA 却可达，故非网络代理问题）。使用前请到对应平台搜索最新仓库；本表中的字段为本平台按已知格式识别（FAQ 问答/摘要），若仓库地址有变以上表链接站点为准。
- **Huatuo-26M**、**DISC-Law-SFT** 为 HuggingFace 数据集（`load_dataset` 加载后转 jsonl/csv 上传），信息以 HF 卡片为准；Huatuo-26M 体量极大务必抽样。
