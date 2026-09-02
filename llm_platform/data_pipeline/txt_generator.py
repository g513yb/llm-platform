"""纯文本 → ShareGPT 问答对：用领域阶段把裸文本结构化后按模板合成（方案② 领域规则抽取）。

原则：抽到结构才合成，否则返回 []（跳过，不产生垃圾样本）。纯 CPU，不依赖 LLM。
仅负责"文本 → 一条问答对"，不做完整 preset（那由 run_pipeline 在 reader 之后统一跑）。
"""
from __future__ import annotations

import re
from typing import Callable

from llm_platform.domain_presets import make_ctx
from llm_platform.domain_presets.engine import WorkItem
from llm_platform.domain_presets.stages_generic import SectionStage
from llm_platform.domain_presets.stages_legal import DocTypeStage, LegalStructureStage


def read_txt_raw(text: str, slug: str) -> list[dict]:
    gen = TXT_GENERATORS.get(slug)
    if gen is None:
        raise ValueError(f"该领域暂不支持纯文本输入（无 read_txt_raw 生成器）：{slug}")
    return gen(text)


def make_txt_reader(slug: str) -> Callable:
    """返回 (text)->list[dict] 的生成器，供 read_inputs 绑定。"""
    return lambda text: read_txt_raw(text, slug)


# ---------------------------------------------------------------- 医疗
def _gen_medical(text: str) -> list[dict]:
    ctx = make_ctx("medical")
    it = WorkItem(0, "raw_txt", [{"role": "user", "content": text}])
    it, _ = SectionStage("section").run(it, ctx)
    s = it.meta.get("sections", {})
    if "主诉" in s and "诊断" in s:
        g = lambda k: s.get(k, "").strip()          # noqa: E731
        answer = "\n".join(part for part in [
            f"主诉：{g('主诉')}",
            f"现病史：{g('现病史')}" if g('现病史') else "",
            f"既往史：{g('既往史')}" if g('既往史') else "",
            f"诊断：{g('诊断')}",
            f"治疗：{g('治疗')}" if g('治疗') else "",
        ] if part)
        return [{"messages": [{"role": "user", "content": text},
                              {"role": "assistant", "content": answer}]}]
    return []


# ---------------------------------------------------------------- 法律
def _gen_legal(text: str) -> list[dict]:
    ctx = make_ctx("legal")
    it = WorkItem(0, "raw_txt", [{"role": "user", "content": text}])
    it, _ = DocTypeStage("doc_type").run(it, ctx)
    it, _ = LegalStructureStage("legal_structure").run(it, ctx)
    dt = it.meta.get("doc_type")
    arts = _collect_articles(it.meta.get("clause_tree"))
    if dt == "合同":
        answer = _contract_summary(text, it.meta)
    elif dt == "判决书":
        answer = _judgment_summary(text, it.meta)
    elif arts:
        answer = "\n".join(f"第{a['no']}条要点：{_strip_clause(a['text'])}" for a in arts[:4])
    else:
        return []
    if not answer:
        return []
    return [{"messages": [{"role": "user", "content": text},
                          {"role": "assistant", "content": answer}]}]


def _first_match(text: str, pattern: str) -> str:
    m = re.search(pattern, text)
    return m.group(0).strip() if m else ""


def _parts_get(parts: dict, key: str, limit: int = 200) -> str:
    vals = parts.get(key)
    if vals:
        return "；".join(str(v) for v in vals)[:limit]
    return ""


def _judgment_summary(text: str, meta: dict) -> str:
    parts = meta.get("parts") or {}
    case_no = _first_match(text, r"[（(]20\d{2}[）)][^，。\s]{0,16}?\d+号")
    segs = ["文书类型：判决书"]
    if case_no:
        segs.append(f"案号：{case_no}")
    try:
        parties = _parties(parts)
        if parties:
            segs.append(f"当事人：{'、'.join(parties)}")
    except Exception:
        pass
    hpy = _parts_get(parts, "本院认为")
    if hpy:
        segs.append(f"本院认为：{hpy}")
    jz = _parts_get(parts, "判决主文")
    if not jz and "判决如下" in text:
        jz = "判决如下"
    if jz:
        segs.append(f"判决：{jz[:120]}")
    return "\n".join(s for s in segs if s) if len(segs) > 1 else ""


def _parties(parts: dict) -> list:
    vals = parts.get("当事人") or []
    out = []
    for line in vals:
        line = str(line).strip()
        m = re.match(r"(原告|被告|上诉人|被上诉人|申请人|被申请人)[:：]?\s*([一-龥]{2,3})", line)
        if m:
            out.append(f"{m.group(1)}{m.group(2)}")
    return out


def _contract_summary(text: str, meta: dict) -> str:
    segs = []
    a = re.search(r"甲方[:：]?\s*([一-龥A-Za-z0-9]{2,20})", text)
    b = re.search(r"乙方[:：]?\s*([一-龥A-Za-z0-9]{2,20})", text)
    if a:
        segs.append(f"甲方：{a.group(1)}")
    if b:
        segs.append(f"乙方：{b.group(1)}")
    subject = _first_match(text, r"标的[^。\n]{0,30}|价款[^。\n]{0,20}|金额[^。\n]{0,20}|租金[^。\n]{0,20}")
    if subject:
        segs.append(f"标的/价款：{subject[:80]}")
    clauses = re.findall(r"第[一二三四五六七八九十百零0-9]+条[^。\n]{0,40}", text)
    if clauses:
        segs.append(f"关键条款：{'；'.join(c[:40] for c in clauses[:5])}")
    return "\n".join(segs) if segs else ""


def _collect_articles(node, out=None):
    """递归收集 kind=='条' 的节点。"""
    if out is None:
        out = []
    if not node:
        return out
    if node.get("kind") == "条" and node.get("no") is not None:
        out.append(node)
    for c in node.get("children", []):
        _collect_articles(c, out)
    return out


def _strip_clause(text: str, limit: int = 120) -> str:
    line = (text or "").strip().replace("\n", " ")
    # 去掉第X条 本身，保留条款正文
    line = line.split(" ", 1)[-1] if " " in line else line
    return line[:limit]


TXT_GENERATORS = {"medical": _gen_medical, "legal": _gen_legal}
