# 支持的数据集与使用说明

llm-platform 的「数据治理」可直接读取阿里/清华等来源的**医疗、法律**公开数据集。本文给出各数据的**获取方式、字段、推荐预设、上传前处理**。上传后统一在「数据治理」Tab 选**领域 + 预设**即可清洗落盘。

> 说明：以下字段/加载方式按各仓库 README 与实测样本核对；因网络限制暂无法在线抓取部分卡片原文，加载名称以各仓库为准（均给出链接）。

## 通用：如何把数据喂给 llm-platform

- **HuggingFace 数据集**（CMB / DISC-Law-SFT / Huatuo-26M）：用 `datasets` 加载后导出本地文件再上传：
  ```python
  from datasets import load_dataset
  ds = load_dataset("FreedomIntelligence/Huatuo-26M", split="train").select(range(10000))  # 若太大先抽样
  ds.to_json("huatuo.jsonl")   # 或 ds.to_csv("huatuo.csv")
  # 把 huatuo.jsonl 上传到「数据治理」即可
  ```
- **GitHub 仓库**：`git clone <url>` 后，直接上传仓库里的 `.jsonl`/`.csv`；raw 文书 `.txt` 也支持（法律走规则抽取合成问答对）。
- 上传后在「数据治理」Tab：选领域（医疗/法律）→ 选**预设** → 选文件 → 运行治理 → 落盘 ShareGPT。

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
- 性质：USMLE 型医学单选题。
- 获取：见仓库 README 下载链接（或 HuggingFace 镜像）→ 得到 `questions.jsonl`。
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
- 仓库：https://github.com/CSH-LawBench/LawBench
- 性质：法律基准，含法条检索 / 判决预测 / 法律问答 / 法条摘要等子任务。
- 获取：`git clone`；`data/` 下每任务一个 jsonl。
- 字段：各任务不一；本平台支持 **问答(`question/answer`)** 与 **摘要(`article/summary`)** 形态；**法条检索 / 判决预测为评测负载，留待后续「多维度评测」Sprint**。
- 预设：**legal_qa（宽松）**。

### Chinese-Law-Doc
- 仓库：https://github.com/liuhuanyong/Chinese-Law-Doc
- 性质：中文法律文书 / 合同 / 法规 / 案例 **raw 文本**。
- 获取：`git clone`；按文件夹（如 law_doc / law_contract / law_justice）内含 `.txt`。
- 字段：纯文本；llm-platform 的 `txt_generator` 会自动按文书类型合成问答对：**法规→抽取第X条**、**判决书→案号/当事人/本院认为/判决**、**合同→甲方/乙方/标的/关键条款**。
- 预设：合成后在「法律」预设选 **legal_cn（文书严格）** 或 legal_qa。

---

## 预设选择对照

| 数据 | 领域 | 推荐预设 |
|---|---|---|
| CMB-Exam（选择题）| 医疗 | medical_qa |
| CMB-Clin（病例）| 医疗 | medical_cn（或 medical_qa）|
| Toyhom / MedQA / Huatuo-26M | 医疗 | medical_qa |
| DISC-Law-SFT / LawBench(问答·摘要) | 法律 | legal_qa |
| Chinese-Law-Doc（raw 文书）| 法律 | legal_cn（合成后）|

> 医疗/法律各有两个预设：`medical_cn`/`medical_qa`、`legal_cn`/`legal_qa`；前者严格（要求结构/文书要素），后者宽松（仅脱敏/术语/单位 + 质量分），考试问答类选宽松，病历文书类选严格。
