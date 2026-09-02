"""法律专属阶段：文书类型识别 + 层级/文号结构化。复用引擎，由 resources/legal 驱动。"""
from __future__ import annotations

import re

from .engine import Issue, Stage, WorkItem

_NUM = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
        "六": 6, "七": 7, "八": 8, "九": 9}
_UNIT = {"十": 10, "百": 100, "千": 1000}


def cn_to_arabic(s: str) -> str:
    """中文数字（含 十/百）转阿拉伯；纯数字原样返回；异常则返回原文。"""
    if not s:
        return s or ""
    if s.isdigit():
        return s
    total, last = 0, 0
    for ch in s:
        if ch in _NUM:
            last = _NUM[ch]
        elif ch in _UNIT:
            total += (last or 1) * _UNIT[ch]
            last = 0
        else:
            return s  # 未知字符，保留原文
    return str(total + last)


class DocTypeStage(Stage):
    """识别文书类型（判决书/裁定书/调解书/合同/司法解释/法规）→ meta["doc_type"]。"""

    def run(self, item: WorkItem, ctx):
        rules = ctx.resources.doc_types or {}
        issues = []
        dt = self._detect(item.all_text(), rules)
        item.meta["doc_type"] = dt
        if dt and dt != "其他":
            issues.append(Issue("doc_type", "doc.type", "annotated", f"文书类型：{dt}"))
        return item, issues

    @staticmethod
    def _detect(text, rules) -> str:
        if not rules:
            return "其他"
        for name, rule in sorted(rules.items(), key=lambda kv: kv[1].get("order", 99)):
            if all(re.search(p, text) for p in rule.get("require_all", [])) \
               and not any(re.search(x, text) for x in rule.get("exclude_if", [])):
                return name
        return "其他"


class LegalStructureStage(Stage):
    """文号/案号规范化 + 编章节条款项层级解析 + 文书分部。"""

    def run(self, item: WorkItem, ctx):
        res = ctx.resources
        issues = []
        cites = []
        for m in item.messages:
            t = m.get("content", "")
            if res.citation_normalize:
                for pat, rep in res.citation_normalize:
                    t = pat.sub(rep, t)
                m["content"] = t
            if res.citation_keep_re:
                cites.extend(mm.group(0) for mm in res.citation_keep_re.finditer(t))
        if cites:
            item.meta["citations"] = list(dict.fromkeys(cites))

        doc_text = item.messages[0].get("content", "") if item.messages else ""
        tree = self._parse_hierarchy(doc_text, res)
        if tree and tree.get("children"):
            item.meta["clause_tree"] = tree
        parts = self._detect_parts(doc_text, res)
        if parts:
            item.meta["parts"] = parts
        return item, issues

    @staticmethod
    def _detect_parts(text, res) -> dict:
        """非破坏性记录文书分部（不改写文本）：识别 法院/当事人/本院认为/判决主文/尾部 等出现。"""
        alias_map = res.alias_to_canonical
        if not alias_map:
            return {}
        parts: dict = {}
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            for alias in sorted(alias_map, key=len, reverse=True):
                if line.startswith(alias) or re.match(rf"(?:^|\s){re.escape(alias)}", line):
                    parts.setdefault(alias_map[alias], []).append(line)
                    break
        return parts

    def _parse_hierarchy(self, text, res):
        hier = res.hierarchy
        if not hier:
            return None
        markers = hier.get("markers", [])
        level_order = hier.get("level_order", {})
        cn_to_ar = hier.get("cn_to_ar", True)
        root = {"kind": "doc", "no": None, "raw": None, "text": "", "children": []}
        stack, cur = [root], root
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            hit = None
            for mk in markers:
                mm = re.match(mk["regex"], line)
                if mm:
                    hit = (mk["kind"], mm.group(1))
                    break
            if hit:
                kind, raw_no = hit
                no = cn_to_arabic(raw_no) if cn_to_ar else raw_no
                node = {"kind": kind, "no": no, "raw": raw_no, "text": line, "children": []}
                lvl = level_order.get(kind, 6)
                while len(stack) > 1 and level_order.get(stack[-1]["kind"], 6) >= lvl:
                    stack.pop()
                stack[-1]["children"].append(node)
                stack.append(node)
                cur = node
            else:
                cur["text"] = (cur["text"] + "\n" + line).strip() if cur["text"] else line
        return root
