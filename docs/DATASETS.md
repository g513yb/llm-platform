# 支持的数据集与使用说明

llm-platform 的「数据处理」可直接读取阿里/清华等来源的**医疗、法律、金融、教育**公开数据集。本文给出各数据的**获取方式、字段、识别说明**。上传后在「数据处理」Tab 选**领域** + 上传文件即可，reader 按 schema 自动识别格式并落盘 Alpaca。

> 说明：以下字段/加载方式按各仓库 README 与实测样本核对；因网络限制暂无法在线抓取部分卡片原文，加载名称以各仓库为准（均给出链接）。

## 通用：如何把数据喂给 llm-platform

- **HuggingFace 数据集**（CMB / DISC-Law-SFT / Huatuo-26M）：用 `datasets` 加载后导出本地文件再上传：
  ```python
  from datasets import load_dataset
  ds = load_dataset("FreedomIntelligence/Huatuo-26M", split="train").select(range(10000))  # 若太大先抽样
  ds.to_json("huatuo.jsonl")   # 或 ds.to_csv("huatuo.csv")
  # 把 huatuo.jsonl 上传到「数据处理」即可
  ```
- **GitHub 仓库**：`git clone <url>` 后，直接上传仓库里的 `.jsonl`/`.csv`/`.json`/`.parquet`。
- 上传后在「数据处理」Tab：选领域（医疗/法律/金融/教育）→ 选文件 → 运行处理 → 落盘 **Alpaca `{instruction,input,output}`**（训练用）。
- **领域仅标注**：领域不影响数据处理逻辑（reader 只关注 schema），仅用于输出文件命名（如 `medical_alpaca.jsonl`）。

## 自动下载（测试/重建 fixture 流水线）

`tests/download_datasets.py` 可自动获取下表全部数据源到 `tests/fixtures/_downloads/`（**不入库**）：

- **本地预览**：`python tests/download_datasets.py --list` / `--dry-run --all`
- **选择性下载**：`python tests/download_datasets.py --source cmb,toyhom,lawbench`
- **全量下载**：`python tests/download_datasets.py --all [--force] [--limit-files N] [--quiet]`
- **云端一键流水线**（下载→重建 fixtures→跑测试→可视化报告）：
  ```bash
  git add -A && git commit -m "..." && git push origin main
  ssh autodl 'source /etc/network_turbo && cd /root/autodl-tmp/llm-platform && git fetch origin main && git reset --hard origin/main'
  ssh autodl 'cd /root/autodl-tmp/llm-platform && bash tests/cloud_run.sh'   # 云端运行测试流水线
  # 转发端口后浏览器打开 http://localhost:8899/report.html
  ```
- 特性：幂等（已下载跳过，`.done.json` + `--force` 重下）、断点续传 `.part`、失败指数退避重试、逐源进度、
  单源失败不阻断其它、末尾 `manifest.json` 汇总；HuggingFace 源走 HF resolve URL 直下（零第三方依赖），
  可设 `HF_ENDPOINT`（如 `https://hf-mirror.com`）访问镜像；MedQA 的 Google Drive 数据需可选依赖 `gdown`
  （`pip install gdown`），否则提示手动放置到 `tests/fixtures/_downloads/medqa_drive/`。

---

## 医疗

### CMB（CMB-Exam / CMB-Clin）
- 仓库：https://github.com/FreedomIntelligence/CMB （HF 镜像 `FreedomIntelligence/CMB`）
- 性质：医学考试基准 + 临床病例。
- 获取：`git clone https://github.com/FreedomIntelligence/CMB.git && cd CMB && unzip data/CMB.zip -d data/`；或 `load_dataset("FreedomIntelligence/CMB", "exam")` / `("clin")`。
- 字段：
  - CMB-Exam（选择题）：`exam_type / exam_class / exam_subject / question / answer(字母) / question_type / option{A..E}`
  - CMB-Clin（病例问答）：`id / title / description(病历) / QA_pairs[{question, solution}]`（一份病历多组 QA，description 作上下文）

### Toyhom 中文医患对话
- 仓库：https://github.com/Toyhom/Chinese-medical-dialogue-data
- 性质：医患问答，6 科室，约 79 万条。
- 获取：`git clone`；数据在 `Data_数据/<科室>/<科室>x-y.csv`（GBK 编码）。README 也提供 Alpaca 版。
- 字段：`department / title / ask / answer`（CSV，GBK 自动识别）。

### MedQA
- 仓库：https://github.com/jind11/MedQA
- 性质：USMLE 型医学单选题（已按仓库 README 原文核对）。
- 获取：数据经仓库 README 的 **Google Drive 链接**下载；含 US/中国大陆/台湾三个来源，均 **jsonl**（每行一个 dict），并提供 4 选项 / 5 选项版与官方 train/dev/test 划分 → 得到 `*_qbank.jsonl` 等，直接上传 jsonl。
- 字段：`question / options{A..E} / answer_idx(字母) / answer(解析) / meta_info`

### Huatuo-26M
- HF 数据集：https://huggingface.co/datasets/FreedomIntelligence/Huatuo-26M
- 性质：大型中文医患问答，约 2600 万条。
- 获取：`load_dataset("FreedomIntelligence/Huatuo-26M", split="train")`；**数量极大，务必先抽样/选 source 子集**再导出。
- 字段：`question / response`（另有 `answer_type / source`）。

---

## 法律

### DISC-Law-SFT
- HF 数据集：https://huggingface.co/datasets/ShengbinYue/DISC-Law-SFT
- 性质：中文法律指令 SFT 数据集（DISC-LawLLM）。
- 获取：`load_dataset("ShengbinYue/DISC-Law-SFT")` → 导出 jsonl/csv。
- 字段：
  - Pair：`id / input / output`（input/output 直接用）
  - Triplet：`id / reference[] / input / output`（reference 法条拼进 user 作上下文）
- 注：部分数据有英文翻译残留，`_strip_english_translation` 会自动去除英文占比>70% 的段落。

### LawBench
- 仓库：**https://github.com/open-compass/LawBench**（原给出的 CSH-LawBench/LawBench 已 404；相关镜像 [open-mmlab-12/LawBench](https://github.com/open-mmlab-12/LawBench)）
- 性质：法律基准（OpenCompass 集成，20 任务 × 500 例），含法条检索 / 判决预测 / 法律问答 / 法条摘要等。
- 获取：`git clone https://github.com/open-compass/LawBench`；`data/` 下每任务一个 jsonl。
- 字段：各任务不一；本平台支持 `instruction / question / answer` 形态（instruction+question→user，answer→assistant）；**法条检索 / 判决预测为评测负载，留待后续「多维度评测」Sprint**。

### CrimeKG-QA（犯罪知识图谱问答）
- 仓库：**https://github.com/liuhuanyong/CrimeKgAssitant**（犯罪知识图谱 856 类 + 约 20 万法务问答）
- 性质：法律问答语料。
- 字段：`_id{$oid} / question / answers[] / category`（answers 是多段列表，拼接还原完整回答）。

---

## 金融

### FinEval
- 仓库：https://github.com/SUFE-AIFLM-Lab/FinEval
- 性质：金融知识基准（约 2.6 万题）：**学术类选择题**（MCQ 4661 题）+ **行业类开放问答**（1434 题）等。
- 获取：`git clone https://github.com/SUFE-AIFLM-Lab/FinEval`；数据在 `data-v2/`（JSONL，每行一个 dict）。
- 字段：选择题 `question / options{A..D} / answer(字母) [+ Explanation]`；开放问答 `question / answer`。

### fingpt-sentiment-train
- HF 数据集：https://huggingface.co/datasets/FinGPT/fingpt-sentiment-train
- 性质：金融情感倾向分类（一段金融文本 → 正/负/中性标签）。
- 获取：`load_dataset("FinGPT/fingpt-sentiment-train")` → 导出 jsonl/csv/parquet。
- 字段：`instruction / input / output`（Alpaca 格式，news/tweet → sentiment）。

### BloombergGPT
- 说明：**无官方公开数据集**（模型与 FinPile 未开源，仅论文 [arXiv:2303.17564](https://arxiv.org/abs/2303.17564)）。本平台不提供摄入入口；如需金融语料请使用上面的 FinEval / fingpt。

---

## 教育

### MMLU（hendrycks/test，即 MMLU）
- 仓库：https://github.com/hendrycks/test
- 性质：通用多选题基准（57 科目），CSV `question,A,B,C,D,answer`（答案=字母）。
- 获取：`git clone https://github.com/hendrycks/test` → `data/{dev,val,test}/*.csv`。
- 字段：`question / A..D / answer(字母)`。

### CMMLU
- 仓库：https://github.com/haonan-li/CMMLU
- 性质：中文多选题基准（约 67 科目），CSV `Question,A,B,C,D,Answer`（**首字母大写** + 前导序号列，答案=字母）。
- 获取：`git clone https://github.com/haonan-li/CMMLU` → `data/{dev,test}/*.csv`。
- 字段：`Question / A..D / Answer(字母)`（header 首字母大写，reader 做大小写变体查找）。

### EduChat
- 仓库：**https://github.com/ECNU-ICALK/EduChat**（华东师大 ICALK 教育对话大模型；原给出的 `iecsql/EduChat` 已 404，早期为 `icalk-nlp/EduChat`）。
- 性质：中文教育对话/指令数据（出题、批改、心理疏导、辅导、高考咨询等，多为 Alpaca `instruction/input/output`）。
- 获取：见仓库；其教育 SFT 多为指令/问答对（语料量大，仓库以样例/外部为准）。
- 字段：`instruction / input / output`（Alpaca）。

---

## schema 识别说明

reader 按 schema 优先级自动识别（`server/data_pipeline/readers.py` 的 `SCHEMAS` 是单一事实来源）：

1. **病例问答（clin）**：`description + QA_pairs` → 一份病历多组 QA，description 作上下文（CMB-Clin）
2. **选择题（mcq）**：`question + options/option{A..E}/A..D + answer/answer_idx` → 选项拼进 user，答案 `X. 选项内容`（CMB-Exam/MedQA/CMMLU/MMLU/FinEval-MCQ）
3. **问答（qa）**：按 Alpaca(`instruction+output`) > LawBench(`instruction+question+answer`) > DISC-Law(`input+output[/reference]`) > CrimeKG/Huatuo/Toyhom(`question/ask+answers[]/response/answer`) 优先级尝试

识别失败的单条记录跳过并计入 dropped，不阻断整体。复数键兼容：`option/options`、`answer/answer_idx/response`、`input/output`。

## ⚠️ 注意（账号/地址可能变动）
- **LawBench**（`github.com/CSH-LawBench/LawBench`）与 **Chinese-Law-Doc**（`github.com/liuhuanyong/Chinese-Law-Doc`）在本文核对时**返回 404**（可能已迁移/改名/私有化；同是 GitHub 的 MedQA 却可达，故非网络代理问题）。使用前请到对应平台搜索最新仓库；本表中的字段为本平台按已知格式识别（FAQ 问答/摘要），若仓库地址有变以上表链接站点为准。
- **Huatuo-26M**、**DISC-Law-SFT** 为 HuggingFace 数据集（`load_dataset` 加载后转 jsonl/csv 上传），信息以 HF 卡片为准；Huatuo-26M 体量极大务必抽样。
