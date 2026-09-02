"""数据治理门面：run_pipeline(domain, file_paths, ...) -> PipelineSummary。

顺序：reader 归一化 -> 通用逐轮清洗 -> 领域预设级联 -> 合并判定(keep/drop+原因) -> 去重 -> 落盘。
纯 CPU，不加载模型。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import time

from llm_platform.domain import slug as label_to_slug
from llm_platform.domain_presets import build_preset, default_preset, make_ctx
from llm_platform.domain_presets.engine import WorkItem
from . import io as io_mod
from .cleaners import dedupe, generic_clean
from .readers import read_inputs
from .txt_generator import make_txt_reader


@dataclass
class PipelineSummary:
    total: int = 0
    kept: int = 0
    dropped: int = 0
    stage_issues: dict = field(default_factory=dict)
    stage_cleaned: dict = field(default_factory=dict)
    drop_reasons: dict = field(default_factory=dict)
    output_files: list = field(default_factory=list)
    preview: list = field(default_factory=list)
    ok: bool = True
    message: str = ""


def _write_tmp_txt(slug: str, text: str, idx: int) -> str:
    inbox = io_mod.DATA_DIR / "_inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    p = inbox / f"raw_{slug}_{int(time.time())}_{idx}.txt"
    p.write_text(text, encoding="utf-8")
    return str(p)


def _pick_drop(it: WorkItem, params: dict):
    drops = [i for i in it.issues if i.level == "drop"]
    if drops:
        return drops[0].message or "不合格"
    if it.meta.get("domain_score", 1.0) < params["score_cutoff"]:
        return "结构/领域质量分过低"
    L = len(it.all_text())
    if L < params["min_len"]:
        return "长度过短"
    if L > params["max_len"]:
        return "长度过长"
    return None


def _preview_row(it: WorkItem) -> dict:
    top = [i for i in it.issues if i.level in ("warning", "drop")][:4]
    return {
        "id": it.record_id,
        "status": it.status,
        "drop_reason": it.drop_reason or "",
        "top_issues": "；".join(f"[{i.stage}]{i.message}" for i in top)[:200],
    }


def run_pipeline(domain_label: str, file_paths: list[str] | None = None,
                 texts: list[str] | None = None,
                 min_len: int = 10, max_len: int = 2000,
                 dedup: bool = True, score_cutoff: float = 0.4) -> PipelineSummary:
    slug = label_to_slug(domain_label)
    paths = list(file_paths or [])
    # 粘贴的纯文本 -> 临时 .txt，走 .txt→read_txt_raw 同一路径
    for idx, t in enumerate(texts or []):
        t = (t or "").strip()
        if t:
            paths.append(_write_tmp_txt(slug, t, idx))
    if not paths:
        raise ValueError("请先上传数据文件，或粘贴纯文本。")

    params = {"min_len": int(min_len), "max_len": int(max_len),
              "dedup": bool(dedup), "score_cutoff": float(score_cutoff)}
    ctx = make_ctx(slug, params)

    items, meta = read_inputs(paths, read_txt_raw=make_txt_reader(slug))

    # 1) 通用逐轮清洗
    for it in items:
        it.issues.extend(generic_clean(it))

    # 2) 领域预设级联
    preset = build_preset(slug) or default_preset(ctx)
    for it in items:
        preset.run(it, ctx)

    # 3) 判定 keep/drop + 原因
    kept, dropped, drop_reasons = [], [], Counter()
    for it in items:
        reason = _pick_drop(it, params)
        if reason:
            it.status, it.drop_reason = "dropped", reason
            dropped.append(it)
            drop_reasons[reason] += 1
        else:
            it.status = "kept"
            kept.append(it)

    # 4) 去重（仅对 kept）
    dd = []
    if params["dedup"] and kept:
        kept, dd = dedupe(kept)
        for _rid, reason in dd:
            drop_reasons[f"去重:{reason}"] += 1
    total_dropped = len(dropped) + len(dd)

    # 5) 落盘
    files = io_mod.write_outputs(kept, slug, params, meta)

    return PipelineSummary(
        total=len(items), kept=len(kept), dropped=total_dropped,
        stage_issues=dict(ctx.stats.issue_ctr), stage_cleaned=dict(ctx.stats.cleaned_ctr),
        drop_reasons=dict(drop_reasons), output_files=files,
        preview=[_preview_row(it) for it in items[:20]],
    )


def format_summary(s: PipelineSummary) -> str:
    """把汇总渲染成 Markdown，供 UI 展示。"""
    lines = [
        f"**总数** {s.total} | **保留** {s.kept} | **丢弃** {s.dropped}",
        "",
        "**阶段处置**" + ("（无领域阶段）" if not s.stage_issues else ""),
        "  - " + "；".join(f"{k}: {v}" for k, v in sorted(s.stage_issues.items())) or "—",
        "",
        "**丢弃原因分布**",
        "  - " + "；".join(f"{k}: {v}" for k, v in sorted(s.drop_reasons.items())) or "—",
    ]
    return "\n".join(lines)
