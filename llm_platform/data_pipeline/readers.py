"""数据读取器：按 SCHEMAS 自动识别格式，转成内部统一格式 messages。

read_all 统一入口，逐条按 schema 优先级尝试 _parse_clin → _parse_mcq → _parse_qa。
识别失败的单条记录跳过并计入 dropped，不阻断整体。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path


#: 支持的源数据集 schema，按数据类型 slug 分组（单一事实来源：在此查看支持哪些数据集及其全部键）。
#: reader 按字段名自动识别，不要求键齐全，但各类型的必备字段见对应 _parse_* 函数。
SCHEMAS: dict[str, dict[str, dict]] = {
    "mcq": {  # 选择题（医疗 / 金融）
        "CMB-Exam": {
            "keys": ["exam_type", "exam_class", "exam_subject", "question",
                     "question_type", "option{A..E}", "answer"],
            "fmt": "json/jsonl",
            "note": "train/val 的 *-merge.json 完整；test 的 question-merge 无 answer（需按 id 合并，暂不支持）",
        },
        "MedQA": {
            "keys": ["question", "options{A..E}", "answer_idx", "answer(解析)", "meta_info"],
            "fmt": "jsonl",
        },
        "CMMLU/MMLU": {
            "keys": ["question", "A", "B", "C", "D", "answer"],
            "fmt": "csv",
        },
        "FinEval-MCQ": {
            "keys": ["id", "question", "A", "B", "C", "D", "answer", "explanation"],
            "fmt": "csv",
            "note": "FinEval 学术选择题（dev/val 有 answer+explanation；test 无 answer 不适合训练）",
        },
    },
    "clin": {  # 医疗病例问答
        "CMB-Clin": {
            "keys": ["id", "title", "description", "QA_pairs[{question, answer}]"],
            "fmt": "json/jsonl",
            "note": "一份病历(description) + 多组问答对；每对转一条样本，description 作上下文",
        },
    },
    "qa": {  # 问答（医疗 / 法律 / 金融）
        "CrimeKG-QA": {
            "keys": ["_id{$oid}", "question", "answers[]", "category"],
            "fmt": "json(每行一对象)",
            "note": "CrimeKG 法律问答语料；answers 取首个",
        },
        "DISC-Law-Pair": {
            "keys": ["id", "input", "output"],
            "fmt": "jsonl",
            "note": "DISC-Law SFT Pair（文书摘要/法律问答等，input/output 直接用）",
        },
        "DISC-Law-Triplet": {
            "keys": ["id", "reference[]", "input", "output"],
            "fmt": "jsonl",
            "note": "DISC-Law SFT Triplet（判决预测/法律问答，reference 法条拼进 user 作上下文）",
        },
        "FinGPT-sentiment": {
            "keys": ["instruction", "input", "output"],
            "fmt": "parquet/jsonl",
            "note": "金融情感分析（news/tweet → sentiment），Alpaca 格式直转 messages",
        },
        "LawBench": {
            "keys": ["instruction", "question", "answer"],
            "fmt": "json",
            "note": "法律评测基准（20类任务×500条），instruction+question→user，answer→assistant",
        },
        "Huatuo-26M": {
            "keys": ["question", "response"],
            "fmt": "parquet",
            "note": "医疗问答（患者提问→医生回答），华佗语料",
        },
        "Toyhom": {
            "keys": ["department", "title", "ask", "answer"],
            "fmt": "csv(GBK)",
            "note": "中文医疗问答（6科室×79万条），ask→user，answer→assistant",
        },
    },
}


def _parse_mcq(rec: dict) -> tuple[str, dict[str, str], str, str] | None:
    """从一条记录解析 (question, options, answer_letter, explanation)；失败返回 None。"""
    q = (rec.get("question") or rec.get("Q") or "").strip()
    if not q:
        return None

    # 选项：优先 option/options/choices dict，其次 optionA/optionB/.. 或单字母 A/B/C/D 字段
    opts = rec.get("option") or rec.get("options") or rec.get("choices")
    if isinstance(opts, dict):
        options = {str(k).strip().upper(): str(v).strip() for k, v in opts.items() if v}
    else:
        options = {}
        for k, v in rec.items():
            kk = str(k).strip().upper()
            if kk in ("OPTIONA", "OPTIONB", "OPTIONC", "OPTIOND", "OPTIONE") or (
                len(kk) == 1 and kk in "ABCDE"
            ):
                if v not in (None, ""):
                    options[kk[-1]] = str(v).strip()
    if not options:
        return None

    # 答案字母：优先 answer_idx/response（明确字母），再 answer（可能是解析文本）
    letter = ""
    for key in ("answer_idx", "response", "answer"):
        val = rec.get(key)
        if not val:
            continue
        for ch in str(val).upper():
            if ch in options:
                letter = ch
                break
        if letter:
            break
    if not letter:
        return None

    # 解析：answer 字段若非简短字母则视为解析文本
    expl = ""
    ans_val = str(rec.get("answer", "")).strip()
    if ans_val and not (ans_val.upper().lstrip().startswith(letter) and len(ans_val) <= 3):
        expl = ans_val
    elif rec.get("explanation"):
        expl = str(rec["explanation"]).strip()

    return q, options, letter, expl


def _to_messages(q: str, options: dict[str, str], letter: str, expl: str) -> list[dict]:
    body = q + "\n" + "\n".join(f"{k}. {v}" for k, v in sorted(options.items()))
    ans = f"{letter}. {options[letter]}"
    if expl:
        ans += f"\n\n解析：{expl}"
    return [{"role": "user", "content": body}, {"role": "assistant", "content": ans}]


def _sniff_csv_encoding(path: Path) -> str:
    """读前 4KB 探测 CSV 编码：utf-8-sig 优先，失败回退 gb18030。"""
    with path.open("rb") as f:
        chunk = f.read(4096)
    for enc in ("utf-8-sig", "gb18030"):
        try:
            chunk.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "gb18030"


def _iter_records(path: Path):
    """按文件扩展名逐条 yield dict 记录。"""
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)
    elif suffix == ".json":
        text = path.read_text(encoding="utf-8")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # 每行一个 JSON 对象（MongoDB 导出风格，字段间带空格）
            for line in text.splitlines():
                line = line.strip()
                if line:
                    yield json.loads(line)
            return
        rows = data if isinstance(data, list) else data.get("data") or data.get("items") or []
        for r in rows:
            yield r
    elif suffix == ".csv":
        enc = _sniff_csv_encoding(path)
        with path.open(encoding=enc, newline="") as f:
            for r in csv.DictReader(f):
                yield r
    elif suffix == ".parquet":
        import pandas as pd
        for r in pd.read_parquet(path).to_dict("records"):
            yield r
    # 其他扩展名忽略


def _parse_clin(rec: dict) -> list[list[dict]]:
    """从一条病例记录解析出多条 messages（一个病历多组QA）；空则 []。"""
    desc = (rec.get("description") or "").strip()
    qa = rec.get("QA_pairs") or []
    if not desc or not qa:
        return []
    out = []
    for pair in qa:
        q = (pair.get("question") or "").strip()
        a = (pair.get("answer") or pair.get("solution") or "").strip()
        if q and a:
            out.append([
                {"role": "user", "content": f"{q}\n\n病历：\n{desc}"},
                {"role": "assistant", "content": a},
            ])
    return out


def _parse_qa(rec: dict) -> list[dict] | None:
    """解析问答类记录 -> messages 或 None。
    按 schema 优先级：
      Alpaca(instruction+output) > LawBench(instruction+question+answer)
      > DISC-Law(input+output[/reference]) > CrimeKG/Huatuo/Toyhom(question/ask+answers[]/response/answer)
    """
    inst = (rec.get("instruction") or "").strip()
    inp = (rec.get("input") or "").strip()
    out = (rec.get("output") or "").strip()
    # Alpaca: instruction + output（FinGPT）
    if inst and out:
        user = f"{inst}\n\n{inp}" if inp else inst
        return [{"role": "user", "content": user}, {"role": "assistant", "content": out}]
    # LawBench: instruction + question + answer
    q = (rec.get("question") or "").strip()
    a = (rec.get("answer") or "").strip()
    if inst and q and a:
        return [{"role": "user", "content": f"{inst}\n\n{q}"}, {"role": "assistant", "content": a}]
    # DISC-Law: input + output（Triplet 的 reference 法条拼进 user 作上下文）
    if inp and out:
        ref = rec.get("reference") or []
        if isinstance(ref, list) and ref and ref[0][:30] not in inp:
            inp = "参考法条：\n" + "\n".join(str(r) for r in ref) + "\n\n" + inp
        return [{"role": "user", "content": inp}, {"role": "assistant", "content": out}]
    # CrimeKG/Huatuo/Toyhom: question/ask + answers[]/response/answer
    # q 可能已被 LawBench 分支设为 question；a 可能已被设为 answer（Toyhom 靠此复用）
    q = (q or (rec.get("ask") or "").strip())
    ans = rec.get("answers") or rec.get("response") or ""
    if isinstance(ans, list) and ans:
        a = str(ans[0]).strip()
    elif isinstance(ans, str) and ans.strip():
        a = ans.strip()
    if q and a:
        return [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
    return None


def read_all(file_paths: list[str], limit: int = 0) -> tuple[list[list[dict]], int, dict]:
    """统一读取：自动识别病例问答/选择题/问答 -> (messages, 丢弃数, 类型计数)。
    逐条按 schema 优先级尝试：病例问答(QA_pairs) → 选择题(question+options) → 问答(Alpaca/DISC-Law/CrimeKG)。
    领域不影响处理逻辑，仅由调用方用于标注/输出命名。
    """
    items, dropped, counts = [], 0, {}
    for p in file_paths:
        for rec in _iter_records(Path(p)):
            if limit and len(items) >= limit:
                return items, dropped, counts
            clin = _parse_clin(rec)
            if clin:
                items.extend(clin)
                counts["病例问答"] = counts.get("病例问答", 0) + len(clin)
                continue
            parsed = _parse_mcq(rec)
            if parsed is not None:
                items.append(_to_messages(*parsed))
                counts["选择题"] = counts.get("选择题", 0) + 1
                continue
            msgs = _parse_qa(rec)
            if msgs is not None:
                items.append(msgs)
                counts["问答"] = counts.get("问答", 0) + 1
                continue
            dropped += 1
    return items, dropped, counts