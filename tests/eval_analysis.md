# 模型评估：问题分析与解决方案

## 评估范围
26 个 pipeline 测试用例的实际 Alpaca 输出，由 GLM-5.2 逐条评估。

## 问题清单（按严重程度排序）

### P0：兜底数据冒充其他领域（5 个用例，严重）

| # | 用例 | 现象 | 根因 | 下载目录状态 |
|---|------|------|------|-------------|
| 1 | `test_fineval_mcq` | 医学题冒充金融选择题 | `build_fineval` 兜底用 CMB-Exam 重排 | .rar 未解压 |
| 2 | `test_fineval_qa` | 医疗咨询冒充金融问答 | `build_fineval` 兜底用 Toyhom 重排 | .rar 未解压 |
| 3 | `test_medqa` | CMB-Exam 冒充 MedQA | `build_medqa` 兜底，Google Drive 不可达 | 空目录 |
| 4 | `test_disc_law` | LawBench 纠错冒充 DISC-Law-SFT | `build_disc_law` 兜底，下载失败 | 空目录 |
| 5 | `test_mmlu` | CMMLU 中文题冒充 MMLU 英文题 | `build_edu_mcq` 代码 bug：`mr["A"]` 应为 `mr["a"]` | CSV 存在但未读到 |

### P1：兜底解析为无意义模板（2 个用例）
- MedQA：解析=`"结合题干与选项，正确答案应为首项（示例解析）"`，且"首项"与实际答案不符
- FinEval MCQ：解析=`"结合题干与选项分析可得（示例解析）"`

### P2：数据质量参差（2 个用例）
- Toyhom：口语化+错别字（"发觉"→发现，"糖尿并"→糖尿病）+语句不通顺
- fingpt：英文金融新闻与中文平台不匹配

### P3：样本量不足（4 个用例）
- MMLU 仅 1 行（应有 135+ 行可用）
- CMMLU 仅 4 行（agronomy dev 集本身小）
- EduChat 仅 1 行构造数据
- 多个 _cn 预设用例仅 1 行构造数据

### P4：格式不一致
- CMMLU 全角冒号 `答案：D` vs CMB-Exam 半角 `答案:D`

---

## 解决方案

### 方案 1：修复 MMLU CSV 列名大小写 bug（P0-#5，立即可做）

**文件**：`tests/build_fixtures.py` 第 462-463 行

**问题**：MMLU CSV 列名是小写 `a,b,c,d`，代码用 `mr["A"]`（大写）访问 → KeyError

**修复**：
```python
# 第 462 行：mr["A"] → mr["a"]
mmlu_rows.append({"question": str(mr["question"]), "A": str(mr["a"]), "B": str(mr["b"]),
                  "C": str(mr["c"]), "D": str(mr["d"]), "answer": str(mr["answer"])})
```

**效果**：MMLU fixture 从 1 行 → 100 行真实英文多领域题目

### 方案 2：解压 FinEval .rar 文件（P0-#1,#2）

**文件**：`tests/fixtures/_downloads/fineval/data-v2/` 下有两个 .rar

**修复**：用 Python `rarfile` 库或 7z 解压 .rar → 得到 .jsonl 真实金融题

**效果**：FinEval MCQ/QA 从医学/医疗兜底 → 真实金融选择题/问答

### 方案 3：改进兜底逻辑——领域内构造替代跨领域重排（P0-#1~#4）

**原则**：兜底数据必须在同一领域内构造，不能跨领域重排

**修复**：
- `build_fineval` 兜底：用金融知识构造题（如"市盈率计算"、"GDP增长率"）替代 CMB-Exam 医学题
- `build_medqa` 兜底：用医学知识构造题替代 CMB-Exam 重排，或直接标注为 CMB-Exam 子集
- `build_disc_law` 兜底：用法律知识构造替代 LawBench 纠错重排

### 方案 4：重新下载 DISC-Law-SFT（P0-#4）

**问题**：`disc_law/` 目录为空，下载失败

**修复**：检查 download_datasets.py 中 DISC-Law 的下载逻辑，重新下载

### 方案 5：MedQA 替代下载源（P0-#3）

**问题**：Google Drive 不可达（代理限制）

**修复**：改用 HuggingFace 上的 MedQA 镜像（如 `medqa/us` 或类似）

### 方案 6：统一 output 格式（P4）

**修复**：reader 中统一 `答案：` → `答案:`（半角冒号）

---

## 优先级排序

| 优先级 | 方案 | 难度 | 影响 |
|--------|------|------|------|
| 1 | 方案 1：MMLU 列名 bug | 1 行改动 | MMLU 1→100 行 |
| 2 | 方案 3：兜底领域内构造 | 中等 | 消除跨领域冒充 |
| 3 | 方案 2：解压 FinEval .rar | 需 rarfile | FinEval 真实数据 |
| 4 | 方案 4：重下 DISC-Law | 需网络 | DISC-Law 真实数据 |
| 5 | 方案 5：MedQA 替代源 | 需网络 | MedQA 真实数据 |
| 6 | 方案 6：统一格式 | 简单 | 格式一致性 |