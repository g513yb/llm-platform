"""资源驱动的通用阶段处理器。医疗/法律/金融/教育复用同一批 stage，差异全在资源表。

提供 stage：deid / section / marker_norm / terminology / units / completeness_qc / quality_score / numeric
"""
from __future__ import annotations

import re
from typing import Optional

from .engine import Issue, Stage, WorkItem


# ---------------------------------------------------------------- Deid
class DeidStage(Stage):
    """分层脱敏：上下文锚定组 -> 高置信裸正则 -> 姓名启发式（低置信只标注不抹除）。"""

    def run(self, item: WorkItem, ctx):
        res = ctx.resources
        guard = res.guard()
        issues = []
        for m in item.messages:
            text = m.get("content", "")
            new_text, ti = self._apply(text, res, guard)
            if new_text != text:
                m["content"] = new_text
            issues.extend(ti)
        return item, issues

    def _apply(self, text, res, guard):
        issues = []
        out = text
        for g in res.deid_groups:
            if g.get("kind") == "name_heuristic":
                out, issues = self._apply_names(out, g, res, guard, issues)
            elif g.get("context_pat"):
                out, issues = self._apply_anchor(out, g, res, issues)
            elif g.get("pat"):
                out, issues = self._apply_bare(out, g, res, issues)
        return out, issues

    def _apply_bare(self, text, g, res, issues):
        edits = []
        for mm in g["pat"].finditer(text):
            if res.overlaps_protected(text, mm.start(), mm.end()):
                continue
            edits.append((mm.start(), mm.end(), g["replacement"]))
        if edits:
            for s, e, rep in reversed(edits):
                text = text[:s] + rep + text[e:]
            issues.append(Issue("deid", f"deid.{g['id']}", g.get("level", "cleaned"),
                                f"脱敏 {g['id']}：{len(edits)} 处"))
        return text, issues

    def _apply_anchor(self, text, g, res, issues):
        exclude = set(g.get("exclude", []))
        edits = []
        for mm in g["context_pat"].finditer(text):
            val = mm.group(2) if (mm.lastindex and mm.lastindex >= 2) else ""
            if val in exclude:
                continue
            if res.overlaps_protected(text, mm.start(), mm.end()):
                continue
            edits.append((mm.start(), mm.end(), f"{mm.group(1)}：{g['replacement']}"))
        if edits:
            for s, e, rep in reversed(edits):
                text = text[:s] + rep + text[e:]
            issues.append(Issue("deid", f"deid.{g['id']}", g.get("level", "cleaned"),
                                f"脱敏 {g['id']}：{len(edits)} 处"))
        return text, issues

    def _apply_names(self, text, g, res, guard, issues):
        sur = g.get("surname_chars", "")
        given = g.get("given_len", [1, 2]) or [1, 2]
        lo, hi = int(given[0]), int(given[-1])
        min_conf = g.get("min_confidence", 0.4)
        repl = g.get("replacement", "[姓名]")
        triggers = g.get("trigger_tokens", [])
        suffixes = g.get("suffix_tokens", [])
        window = int(guard.get("name_context_window", 6))
        anchor_req = bool(guard.get("anchor_required_for_cleaned", True))
        skip_bracket = bool(guard.get("skip_inside_brackets", True))
        compounds = g.get("compound_surnames", []) or []
        compound_alt = "|".join(re.escape(c) for c in compounds) if compounds else "(?!)"
        try:
            # 复姓(2字) 优先，其次单姓；允许中文前置（患者/病人/男等）
            name_re = re.compile(
                rf"(?<![A-Za-z0-9])((?:{compound_alt})|[{sur}])([一-龥]{{{lo},{hi}}})(?=$|[\s，。；：、,.!?！？])")
        except re.error:
            return text, issues
        edits = []
        for m in name_re.finditer(text):
            word = m.group(0)
            if res.is_whitelisted(word) or res.ends_with_whitelisted_suffix(word):
                continue
            if res.overlaps_protected(text, m.start(0), m.end(0)):
                continue
            if skip_bracket and self._inside_brackets(text, m.start(0)):
                continue
            win = text[max(0, m.start(0) - window): m.end(0) + window]
            has_suffix = any(t in win for t in suffixes)
            has_trigger = any(t in win for t in triggers)
            conf = 0.9 if has_suffix else (0.6 if has_trigger else 0.3)
            if conf >= min_conf and (not anchor_req or (has_suffix or has_trigger)):
                edits.append((m.start(0), m.end(0), repl))
            else:
                issues.append(Issue("deid", "deid.patient_name_lowconf", "annotated",
                                    f"疑似姓名待人工确认：{word}"))
        if edits:
            for s, e, rep in reversed(edits):
                text = text[:s] + rep + text[e:]
            issues.append(Issue("deid", "deid.patient_name", "cleaned", "患者姓名脱敏"))
        return text, issues

    @staticmethod
    def _inside_brackets(text, pos):
        for op, cl in (("((", "))"), ("【", "】"), ("（", "）"), ("[", "]")):
            o = text.rfind(op, 0, pos)
            c = text.find(cl, pos)
            if o != -1 and c != -1 and c > pos:
                return True
        return False


# ---------------------------------------------------------------- Section
class SectionStage(Stage):
    """病历小节识别：匹配头部 -> 切分块 -> 重建【小节】+保序 -> meta + 顺序倒置 warning。"""

    def run(self, item: WorkItem, ctx):
        res = ctx.resources
        issues = []
        if not res.section_re or not item.messages:
            return item, issues
        text = item.messages[0].get("content", "")
        blocks, order, violations = self._detect(text, res)
        if len(blocks) >= 2:
            item.messages[0]["content"] = "\n\n".join(f"【{c}】\n{body.strip()}" for c, body in blocks)
            item.meta["sections"] = {c: body for c, body in blocks}
            item.meta["section_order"] = order
            item.meta["section_violations"] = violations
            item.meta["structure_complete"] = True
        if len(set(order)) < 2:
            item.meta["structure_incomplete"] = True
            issues.append(Issue("section", "structure.incomplete", "annotated",
                                "病历缺少可识别的结构化小节"))
        for a, b in violations:
            issues.append(Issue("section", "structure.order", "warning",
                                f"小节顺序异常：{a} -> {b}"))
        return item, issues

    def _detect(self, text, res):
        spans = []
        for m in res.section_re.finditer(text):
            canon = self._map_header(m.group(0), res)
            if canon:
                spans.append((canon, m.start(), m.end()))
        # 合并重叠：挨得太近的头部只保留前一个
        merged = []
        for s in spans:
            if merged and s[1] < merged[-1][2] and s[0] == merged[-1][0]:
                continue
            merged.append(s)
        order = [c for c, _, _ in merged]
        violations = self._inversions(order, res.order_index)
        blocks = self._split(text, merged)
        return blocks, order, violations

    @staticmethod
    def _map_header(header, res):
        for alias in sorted(res.alias_to_canonical.keys(), key=len, reverse=True):
            if re.search(re.escape(alias), header):
                return res.alias_to_canonical[alias]
        return None

    @staticmethod
    def _split(text, spans):
        blocks = []
        for i, (c, s, e) in enumerate(spans):
            body_start = e
            body_end = spans[i + 1][1] if i + 1 < len(spans) else len(text)
            blocks.append((c, text[body_start:body_end]))
        return blocks

    @staticmethod
    def _inversions(order, order_index):
        idx = {name: i for i, name in enumerate(order_index)}
        inv = []
        for i in range(1, len(order)):
            a, b = order[i - 1], order[i]
            if a in idx and b in idx and idx[a] > idx[b]:
                inv.append((a, b))
        return inv


# ---------------------------------------------------------------- Terminology
class TerminologyStage(Stage):
    """错字纠正 + 缩写展开（词边界） + 剂量频次转中文；preserve 词不替换。"""

    def run(self, item: WorkItem, ctx):
        res = ctx.resources
        issues = []
        for m in item.messages:
            text = m.get("content", "")
            new = text
            for typo, good in res.term_typo:
                if typo in new:
                    new = new.replace(typo, good)
                    issues.append(Issue("terminology", "term.typo", "cleaned", f"错字：{typo}→{good}"))
            new = self._apply_rules(res, new, res.term_abbrev, "term.abbrev", "缩写展开", issues)
            new = self._apply_rules(res, new, res.term_latin, "term.latin", "频次换算", issues)
            if new != text:
                m["content"] = new
        return item, issues

    @staticmethod
    def _apply_rules(res, text, rules, code, label, issues):
        edits = []
        for pat, rep in rules:
            for mm in pat.finditer(text):
                if res.overlaps_preserved(text, mm.start(), mm.end()):
                    continue
                edits.append((mm.start(), mm.end(), rep))
        if edits:
            for s, e, rep in reversed(edits):
                text = text[:s] + rep + text[e:]
            issues.append(Issue("terminology", code, "cleaned", f"{label}：{len(edits)} 处"))
        return text


# ---------------------------------------------------------------- Units
class UnitsStage(Stage):
    """单位别名规范化 + 剂量/数值区间校验（限指定小节，避免误判化验值）。"""

    DOSE_SECTIONS = ("现病史", "诊断", "治疗", "医嘱")

    def run(self, item: WorkItem, ctx):
        res = ctx.resources
        issues = []
        for m in item.messages:
            text = m.get("content", "")
            for pat, rep in res.unit_rules:
                text = pat.sub(rep, text)
            m["content"] = text
        # 区间校验：优先扫医疗关键小节文本，否则兜底扫全文本
        body = item.meta.get("sections", {})
        scan = "\n".join(body.get(n, "") for n in self.DOSE_SECTIONS if body.get(n))
        if not scan:
            scan = item.all_text()
        if res.dose_rules and scan:
            dose_re = ctx.scratch.get("dose_re")
            if dose_re is None:
                dose_re = self._build_dose_re(res)
                ctx.scratch["dose_re"] = dose_re
            for m in dose_re.finditer(scan):
                val = float(m["value"])
                unit = m["unit"]
                for rule in res.dose_rules:
                    if rule["unit"] == unit and (val < rule["min"] or val > rule["max"]):
                        issues.append(Issue("units", rule["flag"], rule.get("level", "warning"),
                                            f"剂量/数值可疑：{m.group(0)}"))
        # lab_rules：化验值区间（限 辅助检查/体格检查/现病史 小节，越界 warning 不 drop）
        lab_body = item.meta.get("sections", {})
        lab_scan = "\n".join(lab_body.get(n, "") for n in ("辅助检查", "体格检查", "现病史") if lab_body.get(n))
        if not lab_scan:
            lab_scan = item.all_text()
        for rule, pat in res.lab_rules:
            for mm in pat.finditer(lab_scan):
                try:
                    val = float(mm.group(1))
                except Exception:
                    continue
                if val < rule.get("min", float("-inf")) or val > rule.get("max", float("inf")):
                    issues.append(Issue("units", rule.get("flag", "lab.abnormal"), rule.get("level", "warning"),
                                        f"{rule.get('label', '化验值')} 异常：{mm.group(0)}"))
        return item, issues

    @staticmethod
    def _build_dose_re(res):
        canon = res.units.get("canonical", [])
        aliases = []
        for c in canon:
            aliases.extend(c.get("aliases", []))
        aliases += list(res.units.get("compose", []))
        aliases = sorted({a for a in aliases if a}, key=len, reverse=True)
        if not aliases:
            return None
        alt = "|".join(re.escape(a) for a in aliases)
        try:
            return re.compile(rf"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>{alt})")
        except re.error:
            return None


# ---------------------------------------------------------------- Completeness QC
class CompletenessQCStage(Stage):
    """完整性质检。mode=sections（病历）：必需小节 + 回答孤儿引用 + 结构分；
    mode=regex（法律/金融/教育）：按 checks 正则在全文中校验 require_any/require_all。"""

    def run(self, item: WorkItem, ctx):
        res = ctx.resources
        qc = res.qc
        issues = []
        if qc.get("mode") == "sections":
            self._run_sections(item, qc, res, issues)
        else:
            self._run_regex(item, qc, issues)
        return item, issues

    def _run_sections(self, item, qc, res, issues):
        secs = item.meta.get("sections", {})
        missing = []
        for req in qc.get("required_sections", {}).get("user", []):
            if req not in secs:
                missing.append(req)
        item.meta["missing_required"] = missing or None
        if missing:
            reasons = qc.get("drop_reason", {}).get("missing_required", "必填小节缺失")
            issues.append(Issue("completeness_qc", "clinical.missing_required", "drop",
                                f"{reasons}（缺失：{'、'.join(missing)}）",
                                detail={"missing": missing}))
        # 回答引用缺失小节 -> warning
        if qc.get("assistant_refs_sections"):
            ans = " ".join(m["content"] for m in item.assistant_turns())
            for canon in res.order_index:
                alias_hit = any(a in ans for a in res.section_aliases.get(canon, []))
                if alias_hit and canon not in secs:
                    issues.append(Issue("completeness_qc", "clinical.orphan_ref", "warning",
                                        f"回答引用了缺失的小节：{canon}"))
        score = sum(qc.get("score_weights", {}).get(s, 0) for s in secs)
        item.meta["structure_score"] = score
        item.meta["structure_complete"] = score >= qc.get("min_structure_score", 4)
        self._consistency(item, qc, res, issues)

    def _consistency(self, item, qc, res, issues):
        secs = item.meta.get("sections", {})
        cons = qc.get("consistency", {})
        # 诊断-现病史一致性
        dih = cons.get("diagnosis_in_hpi") if isinstance(cons, dict) else None
        if dih and "诊断" in secs and "现病史" in secs:
            diag_text, hpi_text = secs["诊断"], secs["现病史"]
            for kw in dih.get("disease_keywords", []):
                if kw in diag_text and kw not in hpi_text:
                    issues.append(Issue("completeness_qc", "qc.diag_not_in_hpi", "warning",
                                        f"{dih.get('label', '诊断疾病未出现在现病史')}：{kw}"))
        # 主诉须含时长/主要症状
        zr = cons.get("zhusu_require") if isinstance(cons, dict) else None
        if zr and zr.get("section") in secs and len(secs[zr["section"]].strip()) < zr.get("min_len", 4):
            issues.append(Issue("completeness_qc", "qc.zhusu_too_short", "warning",
                                zr.get("label", "主诉过短")))
        # 必需小节内容过短
        sml = cons.get("section_min_len") if isinstance(cons, dict) else None
        if sml:
            for req in qc.get("required_sections", {}).get("user", []):
                if req in secs and len(secs[req].strip()) < sml.get("min_len", 2):
                    issues.append(Issue("completeness_qc", "qc.section_too_short", "warning",
                                        f"{sml.get('label', '必需小节过短')}：{req}"))

    def _run_regex(self, item, qc, issues):
        # 文档类型感知（法律）：按 meta["doc_type"] 取 per-type 校验
        dtc = qc.get("doc_type_checks")
        if dtc and isinstance(dtc, dict):
            dt = item.meta.get("doc_type") or qc.get("default_type", "其他")
            cfg = dtc.get(dt, dtc.get(qc.get("default_type", "其他"), {}))
            checks = cfg.get("checks", {})
            for key, c in checks.items():
                item.meta[f"qc_ok_{key}"] = bool(re.search(c["regex"], item.all_text())) \
                    if c.get("regex") else False
            req_all = cfg.get("require_all", [])
            if req_all and not all(item.meta.get(f"qc_ok_{k}") for k in req_all):
                lvl = "drop" if cfg.get("drop") else "warning"
                issues.append(Issue("completeness_qc", "qc.missing_all", lvl,
                                    cfg.get("drop_reason", "必备要素缺失")))
            return
        # 原 finance/education 路径（无 doc_type_checks）
        checks = qc.get("checks", {})
        for key, c in checks.items():
            ok = bool(re.search(c["regex"], item.all_text())) if c.get("regex") else False
            item.meta[f"qc_ok_{key}"] = ok
        req_any = qc.get("require_any", [])
        req_all = qc.get("require_all", [])
        if req_any and not any(item.meta.get(f"qc_ok_{k}") for k in req_any):
            reasons = qc.get("drop_reason", {}).get("missing", "必备要素缺失")
            issues.append(Issue("completeness_qc", "qc.missing_any", "drop", reasons))
        if req_all and not all(item.meta.get(f"qc_ok_{k}") for k in req_all):
            reasons = qc.get("drop_reason", {}).get("missing", "必备要素缺失")
            issues.append(Issue("completeness_qc", "qc.missing_all", "drop", reasons))


# ---------------------------------------------------------------- Quality score
class QualityScoreStage(Stage):
    """领域质量分 domain_score ∈ [0,1]，与通用 score_cutoff 叠加（在流水线判定）。"""

    def run(self, item: WorkItem, ctx):
        qc = ctx.resources.qc
        mode = qc.get("mode")
        if mode == "pair":
            # 宽松问答/考试：不要求结构，仅看 user/assistant 均有内容
            has_u = any(str(m.get("content", "")).strip() for m in item.user_turns())
            has_a = any(str(m.get("content", "")).strip() for m in item.assistant_turns())
            item.meta["domain_score"] = round(0.9 if (has_u and has_a) else 0.2, 3)
            return item, []
        if mode == "sections":
            total_w = sum(qc.get("score_weights", {}).values()) or 1
            struct = item.meta.get("structure_score", 0) / total_w
            completeness = 0.0 if item.meta.get("missing_required") else 1.0
        else:
            keys = list(qc.get("checks", {}))
            ok = sum(1 for k in keys if item.meta.get(f"qc_ok_{k}"))
            struct = ok / max(1, len(keys))
            completeness = 1.0 if struct > 0 else 0.0
        item.meta["domain_score"] = round(0.6 * struct + 0.4 * completeness, 3)
        return item, []


# ---------------------------------------------------------------- Marker / numeric
class MarkerNormalizeStage(Stage):
    """归一化标记（法律条款编号 / 教育选项·答案），绝不剥离原文。"""

    def run(self, item: WorkItem, ctx):
        res = ctx.resources
        norms = res.structure_norms + res.option_norms
        issues = []
        for m in item.messages:
            text = m.get("content", "")
            new = text
            for pat, rep in norms:
                new, n = pat.subn(rep, new)
                if n:
                    issues.append(Issue("marker_norm", "marker.normalized", "cleaned", f"标记规范化：{n} 处"))
            if new != text:
                m["content"] = new
        return item, issues


class NumericStage(Stage):
    """数值/单位规范化（金融），保留代码/指标/日期。"""

    def run(self, item: WorkItem, ctx):
        res = ctx.resources
        issues = []
        for m in item.messages:
            text = m.get("content", "")
            new = text
            for pat, rep in res.numeric_norms:
                new, n = pat.subn(rep, new)
                if n:
                    issues.append(Issue("numeric", "numeric.normalized", "cleaned", f"数值规范化：{n} 处"))
            if new != text:
                m["content"] = new
        return item, issues
