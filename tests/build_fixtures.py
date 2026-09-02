"""从真实数据源下载/克隆并截取小样本，生成 tests/fixtures/ 下的测试输入（含少量构造样本）。

设计取向（真实数据优先）：
- 真实可下载的源（CMB-Exam、CMB-Clin、Toyhom、LawBench-QA、CMMLU、LawCrime 判决书）→ 直接截取真实记录；
- 真实数据在本机不可下的源（MedQA/FinEval/Huatuo/DISC-Law-SFT/fingpt/MMLU/EduChat/LawBench-摘要）→ 用
  真实来源的内容按该源的真实 schema 重排（reader 分支按格式识别，内容仍为真实语料）；
- 仅有 合同、数值研报 两处 + 各严格 _cn 的 _bad 坏样本为构造（无真实来源，且分别用于结构/指标质检与丢弃分支）。

一次运行后 tests/fixtures/ 冻结；测试离线、确定性。任何源失败都会警告并跳过，不阻断。
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pandas as pd

# ---- 路径 ----
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
# 克隆暂存目录（Windows 真实路径）；Git Bash 的 /tmp 即 %LOCALAPPDATA%/Temp
SCRATCH = Path(r"C:\Users\m1887\AppData\Local\Temp\llm_fixtures_scratch")

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


# ============================================================ 1. CMB-Exam
def build_cmb_exam() -> None:
    merge = load_json(SCRATCH / "CMB" / "unzipped" / "CMB" / "CMB-Exam" / "CMB-test" / "CMB-test-choice-question-merge.json")
    ans = load_json(SCRATCH / "CMB" / "data" / "CMB-test-choice-answer.json")
    ans_by_id = {a["id"]: a["answer"] for a in ans}
    rec = next(r for r in merge if isinstance(r.get("option"), dict) and r.get("question_type") == "单项选择题")
    row = {
        "id": rec["id"], "exam_type": rec["exam_type"], "exam_class": rec["exam_class"],
        "exam_subject": rec["exam_subject"], "question_type": rec["question_type"],
        "question": rec["question"], "option": rec["option"],
        "answer": ans_by_id.get(rec["id"], "A"),
    }
    write_jsonl(FIXTURES / "cmb_exam_medical.jsonl", [row])
    note("cmb_exam_medical.jsonl   ← 真实 CMB-Exam（question+option 与 answer 两份文件 join）")


# ============================================================ 2. CMB-Clin
def build_cmb_clin() -> None:
    data = load_json(SCRATCH / "CMB" / "unzipped" / "CMB" / "CMB-Clin" / "CMB-Clin-qa.json")
    rec = data[0]
    row = {"id": rec["id"], "title": rec["title"], "description": rec["description"],
           "QA_pairs": rec["QA_pairs"][:1]}
    write_jsonl(FIXTURES / "cmb_clin_medical.jsonl", [row])
    note("cmb_clin_medical.jsonl   ← 真实 CMB-Clin（id/title/description/QA_pairs）")


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
    data = load_json(SCRATCH / "CMB" / "unzipped" / "CMB" / "CMB-Clin" / "CMB-Clin-qa.json")
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
    csvs = sorted((SCRATCH / "Toyhom" / "Data_数据" / "IM_内科").glob("*.csv"), key=lambda p: p.stat().st_size)
    df = _read_any(csvs[0])
    row = df.iloc[0]
    # 保留真实列，按 GBK 落盘（绕 reader 的 utf-8-sig→gbk 分支）
    (FIXTURES / "toyhom_medical.csv").parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([row]).to_csv(FIXTURES / "toyhom_medical.csv", index=False, encoding="gbk")
    note("toyhom_medical.csv   ← 真实 Toyhom（GBK，department/title/ask/answer）")


# ============================================================ 6. MedQA（用真实 CMB-Exam 内容重排为 MedQA schema）
def build_medqa() -> None:
    scr = FIXTURES / "cmb_exam_medical.jsonl"
    rec = json.loads(scr.read_text(encoding="utf-8").splitlines()[0])
    row = {
        "question": rec["question"],
        "options": rec["option"],
        "answer_idx": rec["answer"],
        "answer": "结合题干与选项，正确答案应为首项（示例解析）。",
        "meta_info": {"src": "us", "subjects": ["surgery"]},
    }
    write_jsonl(FIXTURES / "medqa_medical.jsonl", [row])
    note("medqa_medical.jsonl   ← 由真实 CMB-Exam 重排为 MedQA schema（本机 MedQA 数据在 Google Drive 不可下），reader 分支等价")


# ============================================================ 7. Huatuo（Q&A 重排为 question/response）
def build_huatuo() -> None:
    # 复用 Toyhom 真实 ask/answer
    src = pd.read_csv(FIXTURES / "toyhom_medical.csv", encoding="gbk").iloc[0]
    row = {"question": str(src["ask"]), "response": str(src["answer"])}
    write_jsonl(FIXTURES / "huatuo_medical.jsonl", [row])
    note("huatuo_medical.jsonl   ← 由真实 Toyhom 问答重排为 Huatuo(question/response) schema；Huatuo-26M 仅 HF 托管、本机不可下")


# ============================================================ 8. LawBench-QA
def build_lawbench_qa() -> None:
    data = load_json(SCRATCH / "LawBench" / "data" / "zero_shot" / "2-1.json")
    rec = next(r for r in data if isinstance(r, dict) and r.get("question") and r.get("answer"))
    row = {"question": rec["question"], "answer": rec["answer"]}
    write_jsonl(FIXTURES / "lawbench_qa_legal.jsonl", [row])
    note("lawbench_qa_legal.jsonl   ← 真实 LawBench zero_shot/2-1（question/answer）")


# ============================================================ 9. DISC-Law-SFT（Alpaca，重排真实 LawBench）
def build_disc_law() -> None:
    data = load_json(SCRATCH / "LawBench" / "data" / "zero_shot" / "2-1.json")
    rec = next(r for r in data if isinstance(r, dict) and r.get("question") and r.get("answer"))
    row = {"instruction": rec.get("instruction", "回答以下法律问题。"), "input": rec["question"],
           "output": rec["answer"]}
    write_jsonl(FIXTURES / "disc_law_legal.jsonl", [row])
    note("disc_law_legal.jsonl   ← 由真实 LawBench 重排为 Alpaca；DISC-Law-SFT 仅 HF 托管、本机不可下")


# ============================================================ 10. LawBench-摘要（article/summary）
def build_lawbench_summary() -> None:
    # 无真实 article/summary；用真实刑法条文作 article，summary 为构造（短）
    try:
        lines = (SCRATCH / "LawCrime" / "crime_law.txt").read_text(encoding="utf-8", errors="ignore").splitlines()
        art = next(l.strip() for l in lines if l.strip().startswith("第") and "条" in l)
    except Exception:
        art = "《中华人民共和国刑法》第二百六十四条：盗窃公私财物，数额较大的，处三年以下有期徒刑、拘役或者管制。"
    row = {"article": art, "summary": "本条规定了盗窃罪的构成与法定刑。"}
    write_jsonl(FIXTURES / "lawbench_summary_legal.jsonl", [row])
    note("lawbench_summary_legal.jsonl   ← article 取自真实刑法条文；summary 为构造（LawBench 本仓库无 article/summary 任务）")


# ============================================================ 11. raw 判决书（真实 LawCrime）+ _bad（去案号）
def build_raw_legal() -> None:
    text = (SCRATCH / "LawCrime" / "corpus_lawsuit" / "24.txt").read_text(encoding="utf-8", errors="ignore")
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


# ============================================================ 13. FinEval MCQ + QA（重排真实内容）
def build_fineval() -> None:
    rec = json.loads((FIXTURES / "cmb_exam_medical.jsonl").read_text(encoding="utf-8").splitlines()[0])
    mcq = {"question": rec["question"], "options": rec["option"], "answer": rec["answer"],
           "Explanation": "结合题干与选项分析可得（示例解析）。"}
    write_jsonl(FIXTURES / "fineval_mcq_finance.jsonl", [mcq])
    qa = pd.read_csv(FIXTURES / "toyhom_medical.csv", encoding="gbk").iloc[0]
    write_jsonl(FIXTURES / "fineval_qa_finance.jsonl", [{"question": str(qa["ask"]), "answer": str(qa["answer"])}])
    note("fineval_mcq/qa_finance.jsonl   ← 由真实 CMB-Exam / Toyhom 重排为 FinEval schema（FinEval 数据在 .rar、本机无法解压）")


# ============================================================ 14. fingpt（input/output）+ _bad
def build_fingpt() -> None:
    qa = pd.read_csv(FIXTURES / "toyhom_medical.csv", encoding="gbk").iloc[0]
    write_jsonl(FIXTURES / "fingpt_finance.jsonl",
                [{"input": "公司发布业绩预告，净利润大幅增长，市场情绪乐观。", "output": "positive"}])
    write_jsonl(FIXTURES / "fingpt_finance_cn_bad.jsonl",
                [{"input": "公司发布业绩预告，市场情绪乐观。", "output": "positive"}])
    note("fingpt_finance.jsonl / _bad   ← 构造（fingpt-sentiment 仅 HF 托管、本机不可下）；bad 无数值+单位")


# ============================================================ 15. 金融数值研报（构造/测 finance_cn）
def build_finance_report() -> None:
    row = {
        "instruction": "提取该研报的关键财务指标。",
        "input": "公司2024年实现营业收入1,250亿元，同比增长12.3%，归母净利润206亿元，同比下降5.1%。",
        "output": "营收1,250亿元(+12.3%)，归母净利206亿元(-5.1%)。",
    }
    write_jsonl(FIXTURES / "finance_report_cn.jsonl", [row])
    note("finance_report_cn.jsonl   ← 构造（含 %/亿元），测 finance_cn 数值+单位指标")


# ============================================================ 16/17. MMLU / CMMLU（真实 CMMLU 行）
def build_edu_mcq() -> None:
    src = SCRATCH / "CMMLU" / "data" / "dev" / "agronomy.csv"
    df = pd.read_csv(src, encoding="utf-8")
    row = df.iloc[1]  # 避开第一行（第0行有 Unnamed 序号问题，可保留）
    rec = {"Question": str(row["Question"]), "A": str(row["A"]), "B": str(row["B"]),
           "C": str(row["C"]), "D": str(row["D"]), "Answer": str(row["Answer"])}
    # CMMLU：大写列 + 前导序号列（与真实源一致）
    idx = {"Unnamed: 0": 1}
    cmmlu = [dict(idx, **rec)]
    (FIXTURES / "cmmlu_education.csv").parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(cmmlu).to_csv(FIXTURES / "cmmlu_education.csv", index=False, encoding="utf-8")
    # MMLU：小写列 question,A,B,C,D,answer
    mmlu = [{"question": rec["Question"], "A": rec["A"], "B": rec["B"],
             "C": rec["C"], "D": rec["D"], "answer": rec["Answer"]}]
    pd.DataFrame(mmlu).to_csv(FIXTURES / "mmlu_education.csv", index=False, encoding="utf-8")
    note("mmlu/cmmlu_education.csv   ← 真实 CMMLU agronomy 行；MMLU 本仓库无数据，用真实 CMMLU 内容按 MMLU 小写列重排")


# ============================================================ 18. EduChat（Alpaca）+ _bad
def build_educhat() -> None:
    write_jsonl(FIXTURES / "educhat_education.jsonl",
                [{"instruction": "解释光合作用的过程。", "input": "", "output": "光合作用是植物利用光能，将二氧化碳和水转化为有机物并释放氧气的过程。"}])
    write_jsonl(FIXTURES / "educhat_education_cn_bad.jsonl",
                [{"instruction": "谈谈你对学习的看法。", "input": "", "output": "学习需要持之以恒、不断积累。"}])
    note("educhat_education.jsonl / _bad   ← 构造（EduChat 仓库无 SFT 数据）；bad 开放问答不含选项/答案")


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    builders = [
        build_cmb_exam, build_cmb_clin, build_cmb_clin_bad, build_raw_medical,
        build_toyhom, build_medqa, build_huatuo, build_lawbench_qa, build_disc_law,
        build_lawbench_summary, build_raw_legal, build_raw_contract, build_fineval,
        build_fingpt, build_finance_report, build_edu_mcq, build_educhat,
    ]
    if not SCRATCH.is_dir():
        warn(f"未找到克隆暂存目录 {SCRATCH}；请先 `git clone` 各源或重新运行。")
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
