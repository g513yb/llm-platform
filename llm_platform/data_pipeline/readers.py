"""输入归一化：Alpaca / ShareGPT / CSV(Alpaca|长表|问答列) / CMB-Exam / CMB-Clin / 通用问答 → WorkItem。
纯文本出指令（raw-text instruction generation）为 P2，本模块留 seam。一条 CMB-Clin 记录 → 多条。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from llm_platform.domain_presets.engine import WorkItem

P2_TXT_MSG = (
    "检测到纯文本(.txt)。本 Sprint 仅支持『已含 指令-输出对』的数据（Alpaca/ShareGPT/CSV/CMB/Toyhom）。\n"
    "从原始文本生成指令（raw-text instruction generation）是 P2 扩展点；reader 层已留"
    " `read_txt_raw()` 接口，后续接入即可。"
)

_EXAM_TYPE_LABEL = {
    "单项选择题": "单选题", "考试单选题": "单选题", "单项选择": "单选题",
    "多项选择题": "多选题", "多选题": "多选题", "多项选择": "多选题",
    "填空题": "填空题", "填空": "填空题", "问答题": "问答题", "简答题": "简答题",
    "名词解释": "名词解释", "论述题": "论述题", "qb": "填空题", "qa": "问答题", "qas": "问答题",
}


def read_inputs(paths: list[str], read_txt_raw: Optional[Callable] = None,
                ) -> tuple[list[WorkItem], dict]:
    files = [p for p in paths if p]
    items: list[WorkItem] = []
    skipped: dict = {}
    rid = 0
    for p in files:
        base = Path(p).name
        try:
            recs = _read_file(p, Path(p).suffix.lower(), read_txt_raw)
        except Exception as e:  # noqa: BLE001
            skipped[base] = str(e)[:120]
            continue
        for raw in recs:
            try:
                out = _normalize(raw, base, rid)          # -> list[WorkItem]
            except Exception as e:  # noqa: BLE001
                skipped[f"{base}#{rid}"] = str(e)[:100]
                rid += 1
                continue
            for it in out:
                items.append(it)
                rid += 1
    meta = {"files": len(files), "rows_loaded": len(items), "skipped": skipped}
    return items, meta


# ---------------------------------------------------------------- 文件读取
def _read_file(path: str, ext: str, read_txt_raw: Optional[Callable]) -> list:
    if ext == ".json":
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        return data if isinstance(data, list) else [data]
    if ext == ".jsonl":
        rows = []
        for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows
    if ext == ".csv":
        return _read_csv(path)
    if ext == ".txt":
        lines = [l for l in Path(path).read_text(encoding="utf-8-sig").splitlines() if l.strip()]
        if lines and all(_is_jsonl_line(l) for l in lines):
            return [json.loads(l) for l in lines]
        if read_txt_raw:
            return read_txt_raw(Path(path).read_text(encoding="utf-8-sig"))
        raise ValueError(P2_TXT_MSG)
    raise ValueError(f"不支持的文件类型：{ext}（支持 .json/.jsonl/.csv/.txt）")


def _is_jsonl_line(line: str) -> bool:
    try:
        json.loads(line)
        return True
    except Exception:
        return False


def _read_csv(path: str) -> list:
    df = None
    for enc in ("utf-8-sig", "gbk", "utf-8"):
        try:
            df = pd.read_csv(path, encoding=enc)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    if df is None:
        raise ValueError("CSV 解码失败（尝试 utf-8-sig/gbk/utf-8）")
    if df.empty:
        return []
    cols = {str(c).strip().lower(): c for c in df.columns}
    # ShareGPT 长表 (id, role, content)
    if "messages" in cols or ({"role", "content"} <= set(cols)):
        return _csv_long_to_messages(df, cols)
    # Alpaca 或中文列名
    if {"instruction", "output"} <= set(cols) or {"指令", "输出"} <= set(cols):
        return list(df.to_dict("records"))
    # 问答列（Toyhom: department/title/ask/answer 或 question/answer 等）
    if ({"ask", "answer"} <= set(cols) or {"question", "answer"} <= set(cols)
            or {"ask", "answers"} <= set(cols) or {"question", "answers"} <= set(cols)):
        return _csv_qa_to_sharegpt(df, cols)
    raise ValueError("CSV 需包含 instruction/input/output 列（或 指令/输入/输出、id/role/content、"
                     "或 ask/question+answer 问答列）")


def _csv_long_to_messages(df, cols):
    id_col = cols.get("id") or cols.get("对话id") or df.columns[0]
    role_col = cols.get("role") or cols.get("角色")
    content_col = cols.get("content") or cols.get("内容")
    grouped: dict = {}
    for _, row in df.iterrows():
        gid = row[id_col]
        grouped.setdefault(gid, []).append({"role": str(row[role_col]).strip(),
                                            "content": str(row[content_col]).strip()})
    return [{"messages": v} for v in grouped.values()]


def _csv_qa_to_sharegpt(df, cols):
    qcol = cols.get("ask") or cols.get("question") or cols.get("answers")
    acol = cols.get("answer") or cols.get("answers")
    dcol, tcol = cols.get("department"), cols.get("title")
    out = []
    for _, row in df.iterrows():
        q, a = _cell(row, qcol), _cell(row, acol)
        if not q or not a:
            continue
        pre = []
        d, t = _cell(row, dcol), _cell(row, tcol)
        if d:
            pre.append(f"科室：{d}")
        if t:
            pre.append(f"标题：{t}")
        user = (f"（{'；'.join(pre)}）\n" if pre else "") + q
        out.append({"messages": [{"role": "user", "content": user},
                                 {"role": "assistant", "content": a}],
                    "_meta": {"format": "toyhom", "department": d, "title": t}})
    return out


def _cell(row, col):
    if col is None:
        return None
    v = row[col]
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    s = str(v).strip()
    return s or None


# ---------------------------------------------------------------- 归一化（返回 list）
def _normalize(raw, base: str, rid: int) -> list:   # noqa: C901
    if isinstance(raw, list):                       # 直接嵌套 messages
        return [_mk(rid, base, raw)]
    if not isinstance(raw, dict):
        raise ValueError(f"{base}#{rid}: 期望 对象/数组，得到 {type(raw).__name__}")

    # ① ShareGPT 优先（保护带额外键的混合记录）
    if isinstance(raw.get("messages"), list):
        return [_mk(rid, base, raw["messages"])]
    # ② CMB-Clin：QA_pairs -> 一条记录转 N 条
    if isinstance(raw.get("QA_pairs"), list):
        return _clin_to_items(raw, base, rid)
    # ③ CMB-Exam：question + (question_type 或 option)
    if _is_exam(raw):
        return [_exam_to_item(raw, base, rid)]
    # ④ Alpaca
    if "instruction" in raw or "output" in raw:
        user = str(raw.get("instruction", "")).strip()
        inp = str(raw.get("input") or "").strip()
        if inp:
            user = f"{user}\n\n{inp}"
        return [_mk(rid, base, [{"role": "user", "content": user},
                                {"role": "assistant", "content": str(raw.get("output", "")).strip()}])]
    # ⑤ 中文 Alpaca
    if "指令" in raw or "输出" in raw:
        user = str(raw.get("指令", "")).strip()
        inp = str(raw.get("输入") or "").strip()
        if inp:
            user = f"{user}\n\n{inp}"
        return [_mk(rid, base, [{"role": "user", "content": user},
                                {"role": "assistant", "content": str(raw.get("输出", "")).strip()}])]
    # ⑥ 通用问答兜底 (ask|question)+(answer|answers|response)
    if ("ask" in raw or "question" in raw) and (
            "answer" in raw or "answers" in raw or "response" in raw):
        return [_generic_qa_to_item(raw, base, rid)]
    # ⑦ 法条/条文摘要: article -> summary/output
    if ("article" in raw or "law_article" in raw) and ("summary" in raw or "output" in raw):
        q = str(raw.get("article") or raw.get("law_article") or "").strip()
        s = raw.get("summary") or raw.get("output")
        s = str(s or "").strip()
        if q and s:
            return [_mk(rid, base, [{"role": "user", "content": q},
                                    {"role": "assistant", "content": s}])]
    # ⑧ input+output（无 instruction/question/answer）-> 问答对（如 fingpt-sentiment-train: 文本→标签）
    if ("input" in raw and "output" in raw and "instruction" not in raw
            and "question" not in raw and "answer" not in raw):
        u = str(raw.get("input", "")).strip()
        o = str(raw.get("output", "")).strip()
        if u and o:
            return [_mk(rid, base, [{"role": "user", "content": u},
                                    {"role": "assistant", "content": o}])]

    raise ValueError(f"{base}#{rid}: 无法识别结构（需 Alpaca/ShareGPT/CMB/Toyhom/LawBench/FinEval/fingpt）")


def _mk(rid: int, base: str, msgs) -> WorkItem:
    clean = [{"role": m.get("role"), "content": str(m.get("content", "")).strip()}
             for m in msgs if isinstance(m, dict) and m.get("role") in ("user", "assistant")]
    return WorkItem(rid, f"{base}#{rid}", clean)


def _is_exam(raw: dict) -> bool:
    return ("question" in raw) and ("question_type" in raw or "option" in raw
                                    or "options" in raw or "answer_idx" in raw)


def _exam_to_item(raw, base, rid) -> WorkItem:
    qt = str(raw.get("question_type", "")).strip()
    label = _EXAM_TYPE_LABEL.get(qt, qt or "题")
    header = "；".join(str(x) for x in [raw.get("exam_type"), raw.get("exam_class"),
                                        raw.get("exam_subject")] if x and str(x).strip())
    # MedQA meta_info 可选增强（src/subjects/group）
    mi = raw.get("meta_info")
    if isinstance(mi, dict):
        for k in ("src", "subjects", "group"):
            v = mi.get(k)
            if v:
                v = "、".join(v) if isinstance(v, (list, tuple)) else str(v)
                header = f"{header}；{k}:{v}" if header else f"{k}:{v}"
    user = f"[{header}] " if header else ""
    user += f"{label}：{str(raw.get('question', '')).strip()}"
    opts = _format_options(raw.get("option") or raw.get("options"))
    if opts:
        user += "\n" + opts
    answer_idx = raw.get("answer_idx")
    letter = str(answer_idx).strip().upper() if answer_idx else _norm_answer(raw.get("answer"))
    asst = f"答案：{letter}" if letter else "答案：见解析"
    # MedQA：answer 是长解析文本；仅当用 answer_idx 且 answer 非单字母时追加解析
    if answer_idx:
        exp = str(raw.get("answer") or "").strip()
        if exp and not re.fullmatch(r"[A-Za-z]+", exp):
            asst += f"\n解析：{exp}"
    else:
        for k in ("explanation", "Explanation", "solution", "解析"):
            if raw.get(k):
                asst += f"\n解析：{str(raw[k]).strip()}"
                break
    return WorkItem(rid, f"{base}#{rid}",
                    [{"role": "user", "content": user}, {"role": "assistant", "content": asst}],
                    meta={"format": "cmb_exam", "question_type": qt,
                          "answer_raw": raw.get("answer"), "answer_idx": answer_idx,
                          "exam_type": raw.get("exam_type"), "exam_subject": raw.get("exam_subject")})


def _format_options(option) -> str:
    if not option:
        return ""
    lines = []
    if isinstance(option, dict):
        for k in sorted(option.keys(), key=str):
            v = str(option[k]).strip()
            if v:
                lines.append(f"{k}. {v}")
    elif isinstance(option, (list, tuple)):
        for i, v in enumerate(option):
            v = str(v).strip()
            if v:
                lines.append(f"{chr(ord('A') + i)}. {v}")
    return "\n".join(lines)


def _norm_answer(a) -> str:
    s = str(a or "").strip().upper()
    letters = re.findall(r"[A-Z]", s)
    if letters:
        return "".join(dict.fromkeys(letters))   # 保序去重
    return s


def _clin_to_items(raw, base, rid) -> list:
    title = str(raw.get("title", "")).strip()
    desc = str(raw.get("description", "")).strip()
    out = []
    for i, qp in enumerate(raw["QA_pairs"]):
        if not isinstance(qp, dict):
            continue
        q = str(qp.get("question", "")).strip()
        s = str(qp.get("solution", "")).strip()
        if not q or not s:
            continue
        user = "\n".join(x for x in (title, desc, q) if x)
        out.append(WorkItem(rid + i, f"{base}#{rid + i}",
                            [{"role": "user", "content": user}, {"role": "assistant", "content": s}],
                            meta={"format": "cmb_clin", "doc_id": raw.get("id"), "title": title}))
    if not out:
        raise ValueError(f"{base}#{rid}: QA_pairs 均无法解析")
    return out


def _generic_qa_to_item(raw, base, rid) -> WorkItem:
    q = str(raw.get("ask") or raw.get("question") or "").strip()
    a = raw.get("response") or raw.get("answer") or raw.get("answers")
    if isinstance(a, list):
        a = a[0] if a else ""
    a = str(a or "").strip()
    return WorkItem(rid, f"{base}#{rid}",
                    [{"role": "user", "content": q}, {"role": "assistant", "content": a}],
                    meta={"format": "generic_qa"})
