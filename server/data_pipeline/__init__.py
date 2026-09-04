"""数据处理门面：run_pipeline(domain, file_paths) -> PipelineSummary。

设计原则：
1. 严格约束——SUPPORTED 是支持的领域列表（单一事实来源），不在清单内的领域直接报错。
2. 极简——无预设引擎/阶段级联/资源表；reader 按 schema 自动识别，不支持则报错。
3. 领域仅标注——不影响数据处理逻辑，实际处理只关注 schema；领域仅用于输出文件命名。
4. 内部统一 messages，输出 Alpaca。

扩展方式：在 readers.py SCHEMAS 加新 schema + 对应 _parse_* 分支，read_all 自动覆盖。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from domain import labels as _domain_labels, slug as label_to_slug
from . import io as io_mod
from .readers import SCHEMAS, read_all

# —— 支持的领域（仅标注，不影响处理逻辑）——
SUPPORTED: list[str] = _domain_labels()

#: 支持的数据类型（展示用）
_TYPES = "病例问答、选择题、问答"


@dataclass
class PipelineSummary:
    total: int = 0
    kept: int = 0
    dropped: int = 0
    type_counts: dict = field(default_factory=dict)
    output_files: list = field(default_factory=list)
    preview: list = field(default_factory=list)
    ok: bool = True
    message: str = ""


def inspect(domain: str, file_paths: list[str], limit: int = 100) -> tuple[PipelineSummary | None, str]:
    """轻量识别（不落盘）-> (summary, error_msg)。error_msg 非空表示不支持/未识别。
    limit 控制预览条数，足够判断格式即可，不读全量。
    """
    if domain not in SUPPORTED:
        return None, f"不支持的领域：{domain}。当前支持：{SUPPORTED}"
    if not file_paths:
        return None, ""
    items, dropped, counts = read_all(file_paths, limit=limit)
    if not items:
        return None, (
            f"未能识别出支持的数据格式。支持类型：{_TYPES}"
            + f"；预览 {dropped} 条均不匹配（schema 见 readers.py SCHEMAS）。"
        )
    return PipelineSummary(kept=len(items), dropped=dropped, type_counts=counts), ""


def run_pipeline(domain: str, file_paths: list[str]) -> PipelineSummary:
    if domain not in SUPPORTED:
        raise ValueError(f"不支持的领域：{domain}。当前支持：{SUPPORTED}")
    if not file_paths:
        raise ValueError("请先上传数据文件。")

    slug = label_to_slug(domain)
    items, dropped, counts = read_all(file_paths)
    if not items:
        raise ValueError(
            f"未能识别出支持的数据格式。支持类型：{_TYPES}"
            + f"；共 {dropped} 条均不匹配（schema 见 readers.py SCHEMAS）。"
        )
    files = io_mod.write_outputs(items, slug)

    return PipelineSummary(
        total=len(items) + dropped,
        kept=len(items),
        dropped=dropped,
        type_counts=counts,
        output_files=files,
        preview=[_preview(m) for m in items[:20]],
    )


def _preview(messages: list[dict]) -> dict:
    return io_mod.messages_to_alpaca(messages)


def format_summary(s: PipelineSummary) -> str:
    type_str = "、".join(f"{k}: {v}" for k, v in s.type_counts.items()) or "—"
    return (
        f"**总数** {s.total} | **保留** {s.kept} | **丢弃** {s.dropped}\n\n"
        f"**类型分布**：{type_str}\n\n"
        f"**输出**：{', '.join(s.output_files) or '—'}"
    )
