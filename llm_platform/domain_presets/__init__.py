"""领域预设子系统：资源驱动的阶段化处理器引擎。

对外暴露：
- build_preset(slug) / default_preset() : 由 resources 构建领域预设
- make_ctx(slug, params) : 构建 PipelineCtx（含已编译资源）
- STAGE_REGISTRY / make_stage : 供数据管道与测试使用
"""
from __future__ import annotations

from pathlib import Path

from .engine import (
    DomainPreset, Issue, PipelineCtx, Stage, StageStats, WorkItem,
)
from .resources import RESOURCE_DIR, ResourceBundle
from .stages_generic import (  # noqa: F401
    CompletenessQCStage, DeidStage, MarkerNormalizeStage, NumericStage,
    QualityScoreStage, SectionStage, TerminologyStage, UnitsStage,
)
from .stages_legal import DocTypeStage, LegalStructureStage  # noqa: F401

STAGE_REGISTRY = {
    "deid": DeidStage,
    "section": SectionStage,
    "terminology": TerminologyStage,
    "units": UnitsStage,
    "completeness_qc": CompletenessQCStage,
    "quality_score": QualityScoreStage,
    "marker_norm": MarkerNormalizeStage,
    "numeric": NumericStage,
    "doc_type": DocTypeStage,
    "legal_structure": LegalStructureStage,
}


def make_stage(kind: str, params: dict | None = None) -> Stage:
    cls = STAGE_REGISTRY.get(kind)
    if cls is None:
        raise KeyError(f"unknown stage kind: {kind!r}")
    p = params or {}
    return cls(name=kind, params=p, enabled=p.get("enabled", True))


def make_ctx(slug: str, params: dict | None = None, resource_dir: Path | None = None) -> PipelineCtx:
    bundle = ResourceBundle.load(slug, resource_dir)
    return PipelineCtx(slug=slug, params=params or {}, resources=bundle)


def build_preset(slug: str, resource_dir: Path | None = None) -> DomainPreset:
    """从 resources/<slug>/preset.json 构建预设；缺失则回落通用（仅质量过滤）。"""
    ctx = make_ctx(slug, resource_dir=resource_dir)
    p = resource_dir or RESOURCE_DIR
    preset_path = p / slug / "preset.json"
    if preset_path.exists():
        return DomainPreset.from_json(preset_path, ctx)
    return default_preset(ctx)


def default_preset(ctx: PipelineCtx | None = None) -> DomainPreset:
    return DomainPreset("generic", "通用预设（无领域阶段，仅质量过滤）",
                        [QualityScoreStage("quality_score")])


def discover_presets(resource_dir: Path | None = None) -> list[str]:
    """列出存在 preset.json 的领域 slug。"""
    p = resource_dir or RESOURCE_DIR
    if not p.exists():
        return []
    return sorted(d.name for d in p.iterdir() if (d / "preset.json").exists())
