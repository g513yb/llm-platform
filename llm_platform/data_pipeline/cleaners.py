"""通用逐轮清洗（编码/空白/标记去噪）+ 语料级去重。
在领域预设之前运行，基础文本噪声先清理，让领域阶段专注于领域逻辑。
"""
from __future__ import annotations

import hashlib
import re
import unicodedata

from llm_platform.domain_presets.engine import Issue, WorkItem

_URL_RE = re.compile(r"https?://\S+")
_HTML_RE = re.compile(r"<[^>]{1,50}>")
_CITE_RE = re.compile(r"\[\d+\]|【\d+】|\(\d+\)")


def fix_encoding(text: str) -> str:
    if text.startswith("﻿"):
        text = text.lstrip("﻿")
    bad = sum(1 for c in text if c in "Ã¤Ââ€˜�" or 0xE000 <= ord(c) <= 0xF8FF)
    if text and bad / len(text) > 0.08:
        try:
            text = text.encode("latin-1").decode("utf-8")
        except Exception:
            pass
    return text


def strip_whitespace(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)     # 全角→半角（数字/字母/标点）
    text = re.sub(r"[ \t　]+", " ", text)       # 折叠空白（含全角空格）
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_markup(text: str) -> str:
    text = _URL_RE.sub("<URL>", text)
    text = _HTML_RE.sub(" ", text)
    text = _CITE_RE.sub(" ", text)
    return text


def generic_clean_text(text: str) -> str:
    return strip_whitespace(strip_markup(fix_encoding(text)))


def generic_clean(item: WorkItem) -> list[Issue]:
    issues = []
    for m in item.messages:
        orig = m.get("content", "")
        new = generic_clean_text(orig)
        if new != orig:
            m["content"] = new
            issues.append(Issue("generic_clean", "text.rewritten", "cleaned", "通用文本清洗"))
    return issues


# ---------------------------------------------------------------- 去重
def norm_text(item: WorkItem) -> str:
    return re.sub(r"\W+", "", " ".join(m.get("content", "") for m in item.messages).lower())


def _shingle(s: str, k: int = 2) -> set:
    return {s[i:i + k] for i in range(len(s) - k + 1)} if len(s) >= k else {s}


def has_near_dup(n: str, existing: list, threshold: float = 0.92) -> bool:
    a = _shingle(n)
    if not a:
        return False
    for e in existing:
        b = _shingle(e)
        if a & b and len(a & b) / max(1, len(a | b)) >= threshold:
            return True
    return False


def dedupe(items: list[WorkItem], threshold: float = 0.92,
           max_compare: int = 200000) -> tuple[list[WorkItem], list[tuple[int, str]]]:
    kept, dropped, seen, kept_norms = [], [], set(), []
    for it in items:
        n = norm_text(it)
        h = hashlib.sha1(n.encode("utf-8")).hexdigest()
        if h in seen:
            dropped.append((it.record_id, "exact_dup"))
            continue
        seen.add(h)
        if len(kept_norms) < max_compare and has_near_dup(n, kept_norms, threshold):
            dropped.append((it.record_id, "near_dup"))
            continue
        kept.append(it)
        kept_norms.append(n)
    return kept, dropped
