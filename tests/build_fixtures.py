"""从真实数据源下载/克隆并截取小样本，生成 tests/fixtures/ 下的测试输入（含少量构造样本）。

设计取向（真实数据优先）：
- 真实可下载的源（CMB-Exam、CMB-Clin、Toyhom、LawBench-QA、CMMLU、LawCrime 判决书）→ 直接截取真实记录；
- 真实数据在本机不可下的源（MedQA/FinEval/Huatuo/DISC-Law-SFT/fingpt/MMLU/EduChat/LawBench-摘要）→ 用
  真实来源的内容按该源的真实 schema 重排（reader 分支按格式识别，内容仍为真实语料）；
- 仅有 合同、数值研报 两处 + 各严格 _cn 的 _bad 坏样本为构造（无真实来源，且分别用于结构/指标质检与丢弃分支）。

一次运行后 tests/fixtures/ 冻结；测试离线、确定性。任何源失败都会警告并跳过，不阻断。
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from pathlib import Path

import pandas as pd

# ---- 路径 ----
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
# 克隆暂存目录：默认 tests/fixtures/_downloads（download_datasets.py 落盘处，不入库）；
# 可用环境变量 LLM_FIXTURES_SCRATCH 覆盖（旧版为 %LOCALAPPDATA%/Temp/llm_fixtures_scratch）
SCRATCH = Path(os.environ.get("LLM_FIXTURES_SCRATCH", str(FIXTURES / "_downloads")))
# --check 模式校验的关键产物（云端流水线在测试前先确保它们存在）
KEY_FIXTURES = [
    "cmb_exam_medical.jsonl", "cmb_clin_medical.jsonl", "toyhom_medical.csv",
    "lawbench_qa_legal.jsonl", "raw_legal_judgment.txt", "cmmlu_education.csv",
    "mmlu_education.csv", "fineval_mcq_finance.jsonl", "fingpt_finance.jsonl",
    "educhat_education.jsonl", "medqa_medical.jsonl", "huatuo_medical.jsonl",
    "disc_law_legal.jsonl", "lawbench_summary_legal.jsonl", "raw_medical.txt",
]
# 每个可扩充源截取的样本数（--samples 覆盖）；单条精选/构造样本不受此影响
SAMPLES = int(os.environ.get("LLM_FIXTURES_SAMPLES", "100"))

rng = random.Random(7)
NOTES: list[str] = []
WARN = []


def note(msg: str) -> None:
    NOTES.append(msg)


def warn(msg: str) -> None:
    WARN.append(msg)
    print(f"[warn] {msg}", file=sys.stderr)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_txt(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ============================================================ 0. 真实数据读取 helper
def _cmb_zipped_root() -> Path:
    """CMB-Exam/CMB-Clin 原始 JSON 在 data/CMB.zip 内，自动解压一次并缓存目录。"""
    out = SCRATCH / "cmb_unzipped"
    if (out / "CMB").is_dir():
        return out / "CMB"
    zip_path = SCRATCH / "cmb" / "data" / "CMB.zip"
    if not zip_path.exists():
        raise FileNotFoundError(
            f"缺少 {zip_path}；请先运行 `python tests/download_datasets.py --source cmb`。"
            "（构建将尝试其它真实源并警告跳过）")
    import zipfile
    zipfile.ZipFile(zip_path).extractall(out)
    return out / "CMB"


def _first_parquet_row(d: Path) -> dict | None:
    """读目录下首个 parquet 的首行（numpy 标量转原生以便 JSON 序列化）；无 pyarrow/无文件返回 None。"""
    try:
        for p in sorted(d.rglob("*.parquet")):
            df = pd.read_parquet(p)
            if len(df):
                return {k: (v.item() if hasattr(v, "item") else v)
                        for k, v in df.iloc[0].to_dict().items()}
    except (ImportError, OSError, ValueError):
        return None
    return None


def _first_jsonl_row(d: Path, **required) -> dict | None:
    """扫目录下 *.jsonl，返回首个含 required 键且非空的首行；找不到返回 None。"""
    for p in sorted(d.rglob("*.jsonl")):
        try:
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                if all(str(r.get(k, "")).strip() for k in required):
                    return r
        except (json.JSONDecodeError, OSError):
            continue
    return None


# ============================================================ 1. CMB-Exam
def build_cmb_exam() -> None:
    merge = load_json(_cmb_zipped_root() / "CMB-Exam" / "CMB-test" / "CMB-test-choice-question-merge.json")
    ans = load_json(SCRATCH / "cmb" / "data" / "CMB-test-choice-answer.json")
    ans_by_id = {a["id"]: a["answer"] for a in ans}
    rows = []
    for rec in merge:
        if isinstance(rec.get("option"), dict) and rec.get("question_type") == "单项选择题":
            rows.append({"id": rec["id"], "exam_type": rec["exam_type"], "exam_class": rec["exam_class"],
                         "exam_subject": rec["exam_subject"], "question_type": rec["question_type"],
                         "question": rec["question"], "option": rec["option"],
                         "answer": ans_by_id.get(rec["id"], "A")})
            if len(rows) >= SAMPLES:
                break
    write_jsonl(FIXTURES / "cmb_exam_medical.jsonl", rows)
    note(f"cmb_exam_medical.jsonl   ← 真实 CMB-Exam（{len(rows)} 条单选题）")


# ============================================================ 2. CMB-Clin
def build_cmb_clin() -> None:
    data = load_json(_cmb_zipped_root() / "CMB-Clin" / "CMB-Clin-qa.json")
    rows = []
    for rec in data:
        rows.append({"id": rec["id"], "title": rec["title"], "description": rec["description"],
                     "QA_pairs": rec["QA_pairs"][:1]})
        if len(rows) >= SAMPLES:
            break
    write_jsonl(FIXTURES / "cmb_clin_medical.jsonl", rows)
    note(f"cmb_clin_medical.jsonl   ← 真实 CMB-Clin（{len(rows)} 条）")


# ============================================================ 3. CMB-Clin _bad（缺主诉+诊断）
def build_cmb_clin_bad() -> None:
    row = {
        "id": "c_bad", "title": "就诊记录",
        "description": "患者因发热、咳嗽前来就诊，要求对症处理，无更多病史描述。",
        "QA_pairs": [{"question": "请问如何处理？", "solution": "多饮水，必要时对症退热。"}],
    }
    write_jsonl(FIXTURES / "cmb_clin_medical_cn_bad.jsonl", [row])
    note("cmb_clin_medical_cn_bad.jsonl   ← 构造：缺主诉/诊断，用于 medical_cn 丢弃分支")


# ============================================================ 4. raw 病历（真实 CMB-Clin description + 诊断）
def build_raw_medical() -> None:
    data = load_json(_cmb_zipped_root() / "CMB-Clin" / "CMB-Clin-qa.json")
    rec = data[0]
    desc = rec["description"]
    dx = ""
    for qp in rec["QA_pairs"]:
        a = qp.get("answer", "")
        if "诊断：" in a:
            dx = a.split("诊断：", 1)[1].split("\n")[0].strip()
            break
    text = desc[:1100] if len(desc) > 1100 else desc
    if dx:
        text += f"\n诊断：{dx}"
    write_txt(FIXTURES / "raw_medical.txt", text)
    note("raw_medical.txt   ← 真实 CMB-Clin 病历（description 截断 + 追加诊断，使 medical_cn 可过主诉/诊断）")


# ============================================================ 5. Toyhom（GBK CSV）
def _read_any(path: Path) -> pd.DataFrame:
    """Toyhom 某些 csv 混有 gb18030-only 字节，按宽容度递增尝试。"""
    for enc in ("utf-8-sig", "gbk", "gb18030", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"无法解码：{path}")


def build_toyhom() -> None:
    csvs = sorted((SCRATCH / "toyhom" / "Data_数据" / "IM_内科").glob("*.csv"), key=lambda p: p.stat().st_size)
    rows = []
    for csv in csvs:
        df = _read_any(csv)
        for _, row in df.iterrows():
            rows.append(row.to_dict())
            if len(rows) >= SAMPLES:
                break
        if len(rows) >= SAMPLES:
            break
    (FIXTURES / "toyhom_medical.csv").parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(FIXTURES / "toyhom_medical.csv", index=False, encoding="gbk")
    note(f"toyhom_medical.csv   ← 真实 Toyhom（{len(rows)} 条，GBK）")


# ============================================================ 6. MedQA（真实优先：Drive 题库；兜底：CMB-Exam 重排）
def build_medqa() -> None:
    rows = []
    for p in sorted((SCRATCH / "medqa_drive").rglob("*.jsonl")):
        try:
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                if r.get("question") and r.get("options") and r.get("answer_idx") and isinstance(r.get("options"), (dict, list)):
                    rows.append({"question": r["question"], "options": r["options"],
                                 "answer_idx": r["answer_idx"], "answer": r.get("answer", ""),
                                 "meta_info": r.get("meta_info", {})})
                    if len(rows) >= SAMPLES:
                        break
        except (json.JSONDecodeError, OSError):
            continue
        if len(rows) >= SAMPLES:
            break
    if rows:
        note(f"medqa_medical.jsonl   ← 真实 MedQA 题库（{len(rows)} 条，_downloads/medqa_drive/）")
    else:
        # 兜底：CMB-Exam 医学题重排为 MedQA schema（同领域，标注真实来源）
        for line in (FIXTURES / "cmb_exam_medical.jsonl").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            rows.append({"question": rec["question"], "options": rec["option"],
                         "answer_idx": rec["answer"], "answer": "",
                         "meta_info": {"src": "cmb_exam", "subjects": ["medical"]}})
            if len(rows) >= SAMPLES:
                break
        note(f"medqa_medical.jsonl   ← 兜底：CMB-Exam 医学题重排为 MedQA schema（{len(rows)} 条，标注 src=cmb_exam）")
    write_jsonl(FIXTURES / "medqa_medical.jsonl", rows)


# ============================================================ 7. Huatuo（真实优先：HF parquet；兜底：Toyhom 重排）
def _parquet_rows(d: Path, n: int, **required) -> list[dict]:
    """读目录下 parquet 前 n 行（含 required 非空键）；无 pyarrow/无文件返回 []。"""
    out = []
    try:
        for p in sorted(d.rglob("*.parquet")):
            df = pd.read_parquet(p)
            for _, r in df.iterrows():
                if all(str(r.get(k, "")).strip() for k in required):
                    out.append({k: (v.item() if hasattr(v, "item") else v) for k, v in r.to_dict().items()})
                    if len(out) >= n:
                        return out
    except (ImportError, OSError, ValueError):
        return []
    return out


def build_huatuo() -> None:
    rows = []
    for r in _parquet_rows(SCRATCH / "huatuo", SAMPLES, question="", response=""):
        rows.append({"question": str(r["question"]), "response": str(r["response"])})
    if rows:
        note(f"huatuo_medical.jsonl   ← 真实 Huatuo-26M（{len(rows)} 条，需 pyarrow）")
    else:
        df = pd.read_csv(FIXTURES / "toyhom_medical.csv", encoding="gbk")
        for _, src in df.iterrows():
            rows.append({"question": str(src["ask"]), "response": str(src["answer"])})
            if len(rows) >= SAMPLES:
                break
        note(f"huatuo_medical.jsonl   ← 兜底：Toyhom 问答重排（{len(rows)} 条）")
    write_jsonl(FIXTURES / "huatuo_medical.jsonl", rows)


# ============================================================ 8. LawBench-QA
def build_lawbench_qa() -> None:
    data = load_json(SCRATCH / "lawbench" / "data" / "zero_shot" / "2-1.json")
    rows = []
    for rec in data:
        if isinstance(rec, dict) and rec.get("question") and rec.get("answer"):
            rows.append({
                "instruction": rec.get("instruction", "回答以下法律问题。"),
                "input": rec["question"],
                "output": rec["answer"],
            })
            if len(rows) >= SAMPLES:
                break
    write_jsonl(FIXTURES / "lawbench_qa_legal.jsonl", rows)
    note(f"lawbench_qa_legal.jsonl   ← 真实 LawBench zero_shot/2-1（{len(rows)} 条，含 instruction 任务描述）")


# ============================================================ 9. DISC-Law-SFT（真实优先：HF parquet Alpaca；兜底：LawBench 重排）
def build_disc_law() -> None:
    rows = []
    for r in _parquet_rows(SCRATCH / "disc_law", SAMPLES, instruction="", output=""):
        rows.append({"instruction": str(r["instruction"]), "input": str(r.get("input", "")), "output": str(r["output"])})
    if rows:
        note(f"disc_law_legal.jsonl   ← 真实 DISC-Law-SFT（{len(rows)} 条，需 pyarrow）")
    else:
        # 兜底：法律领域内构造（法律咨询/法规问答），不重排 LawBench 纠错任务
        disc_fallback = [
            {"instruction": "根据《中华人民共和国民法典》，回答以下法律问题。", "input": "借款合同的诉讼时效是多久？", "output": "根据《民法典》第一百八十八条，向人民法院请求保护民事权利的诉讼时效期间为三年。借款合同属于民事合同，适用三年诉讼时效，自权利人知道或应当知道权利受到损害之日起计算。"},
            {"instruction": "根据《中华人民共和国劳动法》，回答以下法律问题。", "input": "用人单位拖欠工资，劳动者如何维权？", "output": "劳动者可以采取以下途径维权：1) 与用人单位协商；2) 向劳动行政部门投诉，由其责令限期支付；3) 申请劳动仲裁，要求支付拖欠工资及经济补偿；4) 对仲裁裁决不服的，可向人民法院起诉。"},
            {"instruction": "根据《中华人民共和国合同法》，回答以下法律问题。", "input": "合同解除的法定条件有哪些？", "output": "根据《民法典》第五百六十三条，合同解除的法定条件包括：1) 不可抗力致使不能实现合同目的；2) 一方明确表示或以行为表明不履行主要债务；3) 一方迟延履行主要债务，经催告后在合理期限内仍未履行；4) 一方迟延履行致使不能实现合同目的；5) 法律规定的其他情形。"},
            {"instruction": "作为法律顾问，请分析以下案例。", "input": "甲向乙借款10万元，约定一年后归还，未约定利息。一年后甲未归还，乙起诉。", "output": "分析：1) 借款合同有效，甲有还款义务；2) 自然人之间借款未约定利息的，视为无息借款，甲无需支付利息；3) 乙可起诉要求甲偿还本金10万元；4) 自约定还款期限届满之日起三年内乙有权起诉，超过诉讼时效则丧失胜诉权。"},
            {"instruction": "根据《中华人民共和国公司法》，回答以下法律问题。", "input": "有限责任公司的股东最多可以有多少人？", "output": "根据《公司法》第二十四条，有限责任公司由五十个以下股东出资设立。因此有限责任公司股东最多为50人。超过此限度的，应当变更为股份有限公司。"},
        ]
        rows = disc_fallback[:SAMPLES] if SAMPLES <= len(disc_fallback) else disc_fallback
        note(f"disc_law_legal.jsonl   ← 兜底：法律领域内构造（{len(rows)} 条，法律咨询/法规问答）")
    write_jsonl(FIXTURES / "disc_law_legal.jsonl", rows)


# ============================================================ 10. LawBench-摘要（article/summary）
def build_lawbench_summary() -> None:
    # 无真实 article/summary；用真实刑法条文作 article，summary 为构造（短）
    try:
        lines = (SCRATCH / "lawcrime" / "crime_law.txt").read_text(encoding="utf-8", errors="ignore").splitlines()
        art = next(l.strip() for l in lines if l.strip().startswith("第") and "条" in l)
    except Exception:
        art = "《中华人民共和国刑法》第二百六十四条：盗窃公私财物，数额较大的，处三年以下有期徒刑、拘役或者管制。"
    row = {"article": art, "summary": "本条规定了盗窃罪的构成与法定刑。"}
    write_jsonl(FIXTURES / "lawbench_summary_legal.jsonl", [row])
    note("lawbench_summary_legal.jsonl   ← article 取自真实刑法条文；summary 为构造（LawBench 本仓库无 article/summary 任务）")


# ============================================================ 11. raw 判决书（真实 LawCrime）+ _bad（去案号）
def build_raw_legal() -> None:
    text = (SCRATCH / "lawcrime" / "corpus_lawsuit" / "24.txt").read_text(encoding="utf-8", errors="ignore")
    # 去掉 metadata 两行（category/title/publictime），仅保留 content 正文
    body = text.split("content:", 1)[-1]
    write_txt(FIXTURES / "raw_legal_judgment.txt", body.strip())
    # _bad：构造一份"缺案号"判决书（真实判决书正文常含其他案号引用，删一行无法让 has_case_no 失效）
    bad = (
        "某某市中级人民法院\n"
        "刑事判决书\n"
        "公诉机关某某市人民检察院。\n"
        "被告人张三，男，1985年出生。\n"
        "2020年6月1日\n"
        "本院认为，被告人张三的行为已构成盗窃罪。\n"
        "判决如下：被告人张三犯盗窃罪，判处有期徒刑一年。"
    )
    write_txt(FIXTURES / "raw_legal_judgment_cn_bad.txt", bad)
    note("raw_legal_judgment.txt ← 真实 LawCrime corpus_lawsuit/24 刑事判决书；_bad ← 构造缺案号，测 legal_cn 丢弃分支")


# ============================================================ 12. 合同（构造）
def build_raw_contract() -> None:
    text = (
        "甲方：华晟科技有限公司\n"
        "乙方：恒润设备制造有限公司\n"
        "本合同标的为自动化生产线一套，总价款人民币500万元。\n"
        "第1条 甲方应于合同签订后十五日内支付预付款。\n"
        "第2条 乙方应于收到预付款后三十日内交付设备。\n"
        "双方履行本合同发生争议的，协商不成的依法向人民法院起诉。"
    )
    write_txt(FIXTURES / "raw_legal_contract.txt", text)
    note("raw_legal_contract.txt   ← 构造（无真实合同语料来源），测 legal_cn 合同结构")


# ============================================================ 13. FinEval MCQ + QA（真实优先：data-v2 jsonl；兜底：CMB/Toyhom 重排）
def build_fineval() -> None:
    mcq_rows: list[dict] = []
    qa_rows: list[dict] = []
    for p in sorted((SCRATCH / "fineval" / "data-v2").rglob("*.jsonl")):
        try:
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                if r.get("question") and r.get("options") and r.get("answer") and len(mcq_rows) < SAMPLES:
                    mcq_rows.append({"question": r["question"], "options": r["options"], "answer": r["answer"],
                                     "Explanation": r.get("Explanation", r.get("explanation", ""))})
                if r.get("question") and r.get("answer") and not r.get("options") and len(qa_rows) < SAMPLES:
                    qa_rows.append({"question": r["question"], "answer": r["answer"]})
                if len(mcq_rows) >= SAMPLES and len(qa_rows) >= SAMPLES:
                    break
        except (json.JSONDecodeError, OSError):
            continue
        if len(mcq_rows) >= SAMPLES and len(qa_rows) >= SAMPLES:
            break
    if mcq_rows and qa_rows:
        note(f"fineval_mcq/qa_finance.jsonl   ← 真实 FinEval data-v2（mcq {len(mcq_rows)} / qa {len(qa_rows)} 条）")
    else:
        # 兜底：金融领域内构造，不跨领域重排（避免医学题冒充金融题）
        fin_mcq = [
            {"question": "市盈率(P/E)的计算公式是", "options": ["股价/每股收益", "股价/每股净资产", "净利润/营业收入", "总资产/总负债"], "answer": "A", "Explanation": "市盈率=股价/每股收益(EPS)，衡量股价相对盈利的估值水平。"},
            {"question": "下列哪项不属于流动资产", "options": ["货币资金", "应收账款", "固定资产", "存货"], "answer": "C", "Explanation": "固定资产属于非流动资产，其余均为流动资产。"},
            {"question": "GDP平减指数反映的是", "options": ["物价水平变动", "经济增长率", "失业率变化", "汇率变动"], "answer": "A", "Explanation": "GDP平减指数衡量名义GDP与实际GDP之比，反映整体物价水平变动。"},
            {"question": "央行提高存款准备金率的影响是", "options": ["增加货币供给", "减少货币供给", "不影响货币供给", "增加基础货币"], "answer": "B", "Explanation": "提高准备金率减少银行可贷资金，收缩货币供给。"},
            {"question": "下列哪种利率反映了资金的真实借贷成本", "options": ["名义利率", "实际利率", "基准利率", "同业拆借利率"], "answer": "B", "Explanation": "实际利率=名义利率-通货膨胀率，反映真实借贷成本。"},
            {"question": "CAPM模型中β系数的含义是", "options": ["无风险收益率", "市场风险溢价", "资产相对市场的系统性风险", "资产的总风险"], "answer": "C", "Explanation": "β衡量资产收益率相对市场收益率的敏感度，即系统性风险。"},
            {"question": "下列哪项是直接融资方式", "options": ["银行贷款", "发行债券", "信托贷款", "委托贷款"], "answer": "B", "Explanation": "发行债券是资金需求方直接向投资者融资，属于直接融资。"},
            {"question": "巴塞尔协议III对核心一级资本充足率的最低要求是", "options": ["4%", "4.5%", "6%", "8%"], "answer": "B", "Explanation": "巴塞尔III要求核心一级资本充足率不低于4.5%。"},
            {"question": "期权的时间价值在到期时", "options": ["达到最大", "等于内在价值", "趋于零", "保持不变"], "answer": "C", "Explanation": "期权到期时时间价值归零，期权价值等于内在价值。"},
            {"question": "下列哪个指标衡量投资组合的系统性风险", "options": ["标准差", "β系数", "夏普比率", "Alpha"], "answer": "B", "Explanation": "β系数衡量组合相对市场的系统性风险，标准差衡量总风险。"},
        ]
        fin_qa = [
            {"question": "简述货币政策三大工具。", "answer": "货币政策三大工具：公开市场操作（买卖国债调节基础货币）、存款准备金率（控制银行可贷资金规模）、再贴现率（影响银行向央行借款成本）。"},
            {"question": "什么是流动性陷阱", "answer": "流动性陷阱指利率降至极低水平时，人们预期利率只会上升，因而宁愿持有现金而非债券，央行增加货币供给无法进一步降低利率，货币政策失效。"},
            {"question": "解释费雪效应。", "answer": "费雪效应指名义利率约等于实际利率加预期通货膨胀率：i≈r+π^e。表明名义利率随通胀预期调整，实际利率相对稳定。"},
            {"question": "什么是委托代理问题", "answer": "委托代理问题指代理人（如管理层）与委托人（如股东）利益不一致时，代理人可能追求自身利益而非委托人利益，产生道德风险和逆向选择。"},
            {"question": "简述有效市场假说的三种形式。", "answer": "弱式有效（价格反映历史信息）、半强式有效（价格反映所有公开信息）、强式有效（价格反映所有信息含内幕）。信息集递增，超额收益递减。"},
        ]
        mcq_rows = fin_mcq[:SAMPLES] if SAMPLES <= len(fin_mcq) else fin_mcq
        qa_rows = fin_qa[:SAMPLES] if SAMPLES <= len(fin_qa) else fin_qa
        note(f"fineval_mcq/qa_finance.jsonl   ← 兜底：金融领域内构造（mcq {len(mcq_rows)} / qa {len(qa_rows)} 条）")
    write_jsonl(FIXTURES / "fineval_mcq_finance.jsonl", mcq_rows)
    write_jsonl(FIXTURES / "fineval_qa_finance.jsonl", qa_rows)


# ============================================================ 14. fingpt（真实优先：HF parquet，挑无数值+单位的行以测 finance_cn 丢弃；兜底：构造）+ _bad（构造）
def build_fingpt() -> None:
    rows: list[dict] = []
    try:
        for p in sorted((SCRATCH / "fingpt").rglob("*.parquet")):
            df = pd.read_parquet(p)
            for _, r in df.iterrows():
                inp, out = str(r.get("input", "")).strip(), str(r.get("output", "")).strip()
                if not inp or not out:
                    continue
                if re.search(r"\d+(?:\.\d+)?\s*(?:%|亿|万|元|股|吨|米|kg|ml|mg)", inp):
                    continue   # 含数值+单位 → finance_cn 会保留，跳过以保丢弃分支可测
                rows.append({"input": inp, "output": out})
                if len(rows) >= SAMPLES:
                    break
            if len(rows) >= SAMPLES:
                break
    except (ImportError, OSError, ValueError):
        pass
    if rows:
        note(f"fingpt_finance.jsonl   ← 真实 fingpt-sentiment（{len(rows)} 条，挑无数值+单位行，需 pyarrow）")
    else:
        rows = [{"input": "公司发布业绩预告，净利润大幅增长，市场情绪乐观。", "output": "positive"}]
        note("fingpt_finance.jsonl   ← 兜底：构造（fingpt 未下/无 pyarrow/全含数值）")
    write_jsonl(FIXTURES / "fingpt_finance.jsonl", rows)
    write_jsonl(FIXTURES / "fingpt_finance_cn_bad.jsonl",
                [{"input": "公司发布业绩预告，市场情绪乐观。", "output": "positive"}])
    note("  _bad ← 构造（无数值+单位，测 finance_cn 丢弃分支）")


# ============================================================ 15. 金融数值研报（构造/测 finance_cn）
def build_finance_report() -> None:
    row = {
        "instruction": "提取该研报的关键财务指标。",
        "input": "公司2024年实现营业收入1,250亿元，同比增长12.3%，归母净利润206亿元，同比下降5.1%。",
        "output": "营收1,250亿元(+12.3%)，归母净利206亿元(-5.1%)。",
    }
    write_jsonl(FIXTURES / "finance_report_cn.jsonl", [row])
    note("finance_report_cn.jsonl   ← 构造（含 %/亿元），测 finance_cn 数值+单位指标")


# ============================================================ 16/17. MMLU / CMMLU（CMMLU 真实；MMLU 真实优先 data/csv，兜底用 CMMLU 行重排）
def build_edu_mcq() -> None:
    src = SCRATCH / "cmmlu" / "data" / "dev" / "agronomy.csv"
    df = pd.read_csv(src, encoding="utf-8")
    cmmlu_rows = []
    for i, row in df.iterrows():
        if i == 0:
            continue   # 避开第一行（第0行有 Unnamed 序号问题）
        rec = {"Question": str(row["Question"]), "A": str(row["A"]), "B": str(row["B"]),
               "C": str(row["C"]), "D": str(row["D"]), "Answer": str(row["Answer"])}
        cmmlu_rows.append(dict({"Unnamed: 0": i}, **rec))
        if len(cmmlu_rows) >= SAMPLES:
            break
    (FIXTURES / "cmmlu_education.csv").parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(cmmlu_rows).to_csv(FIXTURES / "cmmlu_education.csv", index=False, encoding="utf-8")
    # MMLU：真实优先 _downloads/mmlu/data/{dev,val,test}/*.csv（小写列 question,A..D,answer）
    mmlu_rows: list[dict] = []
    try:
        for p in sorted((SCRATCH / "mmlu" / "data").rglob("*.csv")):
            try:
                mdf = pd.read_csv(p, encoding="utf-8")
            except (UnicodeDecodeError, OSError, pd.errors.ParserError):
                continue
            if {"question", "a", "b", "c", "d", "answer"} <= {str(c).strip().lower() for c in mdf.columns}:
                for _, mr in mdf.iterrows():
                    ans = str(mr["answer"]).strip()
                    if ans.isdigit():
                        ans = "ABCD"[int(ans) % 4]
                    mmlu_rows.append({"question": str(mr["question"]), "A": str(mr["a"]), "B": str(mr["b"]),
                                      "C": str(mr["c"]), "D": str(mr["d"]), "answer": ans})
                    if len(mmlu_rows) >= SAMPLES:
                        break
            if len(mmlu_rows) >= SAMPLES:
                break
    except OSError:
        pass
    if mmlu_rows:
        note(f"mmlu/cmmlu_education.csv   ← 真实 CMMLU agronomy {len(cmmlu_rows)} 行 + 真实 MMLU data csv {len(mmlu_rows)} 行")
    else:
        for c in cmmlu_rows:
            mmlu_rows.append({"question": c["Question"], "A": c["A"], "B": c["B"],
                              "C": c["C"], "D": c["D"], "answer": c["Answer"]})
        note(f"mmlu/cmmlu_education.csv   ← 真实 CMMLU agronomy {len(cmmlu_rows)} 行；MMLU 兜底用 CMMLU 内容按小写列重排 {len(mmlu_rows)} 行")
    pd.DataFrame(mmlu_rows).to_csv(FIXTURES / "mmlu_education.csv", index=False, encoding="utf-8")


# ============================================================ 18. EduChat（真实优先：挑无选项标记的开放问答以测 education_cn 丢弃；兜底：构造）+ _bad（构造）
def _looks_like_mcq(text: str) -> bool:
    return bool(re.search(r"[A-D][.、)]\s|选项|选择题|单选|多选|答案是", text))


def build_educhat() -> None:
    rows: list[dict] = []
    for p in sorted((SCRATCH / "educhat").rglob("*")):
        if p.suffix not in (".jsonl", ".json", ".csv"):
            continue
        try:
            if p.suffix == ".csv":
                df = pd.read_csv(p, encoding="utf-8")
                for _, r in df.iterrows():
                    ins, out = str(r.get("instruction", "")).strip(), str(r.get("output", "")).strip()
                    if ins and out and not _looks_like_mcq(ins):
                        rows.append({"instruction": ins, "input": str(r.get("input", "")), "output": out})
                        if len(rows) >= SAMPLES:
                            break
            else:
                for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if not line.strip():
                        continue
                    r = json.loads(line)
                    ins, out = str(r.get("instruction", "")).strip(), str(r.get("output", "")).strip()
                    if ins and out and not _looks_like_mcq(ins):
                        rows.append({"instruction": ins, "input": str(r.get("input", "")), "output": out})
                        if len(rows) >= SAMPLES:
                            break
            if len(rows) >= SAMPLES:
                break
        except (json.JSONDecodeError, OSError, UnicodeDecodeError, pd.errors.ParserError):
            continue
    if rows:
        note(f"educhat_education.jsonl   ← 真实 EduChat（{len(rows)} 条，挑无选项开放问答以测 education_cn 丢弃）")
    else:
        rows = [{"instruction": "解释光合作用的过程。", "input": "",
                 "output": "光合作用是植物利用光能，将二氧化碳和水转化为有机物并释放氧气的过程。"}]
        note("educhat_education.jsonl   ← 兜底：构造（educhat 未下/无 SFT/全为选择题）")
    write_jsonl(FIXTURES / "educhat_education.jsonl", rows)
    write_jsonl(FIXTURES / "educhat_education_cn_bad.jsonl",
                [{"instruction": "谈谈你对学习的看法。", "input": "", "output": "学习需要持之以恒、不断积累。"}])
    note("  _bad ← 构造（开放问答不含选项/答案，测 education_cn 丢弃分支）")


def main() -> None:
    global SCRATCH, SAMPLES
    ap = argparse.ArgumentParser(prog="build_fixtures.py", description="从下载的数据源截取小样本生成 tests/fixtures/（离线冻结）。")
    ap.add_argument("--check", action="store_true",
                    help="仅校验关键 fixture 文件是否齐全（云端流水线用），不重建")
    ap.add_argument("--scratch", type=Path, default=None,
                    help=f"覆盖源数据目录（默认 {SCRATCH}，也可用 LLM_FIXTURES_SCRATCH 环境变量）")
    ap.add_argument("--samples", type=int, default=SAMPLES,
                    help=f"每个可扩充源截取的样本数（默认 {SAMPLES}；单条精选/构造样本不受影响）")
    args = ap.parse_args()
    if args.scratch:
        SCRATCH = args.scratch
    SAMPLES = args.samples

    if args.check:
        missing = [n for n in KEY_FIXTURES if not (FIXTURES / n).exists()]
        if missing:
            print("== 缺失关键 fixture（请先运行 python tests/download_datasets.py --all 再重建）==")
            for n in missing:
                print(f"  - {n}")
            sys.exit(1)
        print(f"== 关键 fixture 齐全（{len(KEY_FIXTURES)}/{len(KEY_FIXTURES)}）: {FIXTURES}")
        return

    FIXTURES.mkdir(parents=True, exist_ok=True)
    builders = [
        build_cmb_exam, build_cmb_clin, build_cmb_clin_bad, build_raw_medical,
        build_toyhom, build_medqa, build_huatuo, build_lawbench_qa, build_disc_law,
        build_lawbench_summary, build_raw_legal, build_raw_contract, build_fineval,
        build_fingpt, build_finance_report, build_edu_mcq, build_educhat,
    ]
    if not SCRATCH.is_dir():
        warn(f"未找到源数据目录 {SCRATCH}；请先运行 `python tests/download_datasets.py --all` 下载。"
             f"（尚未下载的源将尝试重排/构造兜底）")
    for b in builders:
        try:
            b()
        except Exception as e:  # noqa: BLE001
            warn(f"{b.__name__} 失败：{e}")
    print("==== fixtures 生成完成 ====")
    print(f"目录：{FIXTURES}")
    print("---- 来源说明 ----")
    for n in NOTES:
        print(" ", n)
    if WARN:
        print("---- 警告 ----")
        for w in WARN:
            print(" ", w)


if __name__ == "__main__":
    main()
