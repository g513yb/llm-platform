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
from .resources import RESOURCE_DIR, ResourceBundle, _load, find_preset_config
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


def make_ctx(slug: str, params: dict | None = None, resource_dir: Path | None = None,
             preset: str | None = None) -> PipelineCtx:
    bundle = ResourceBundle.load(slug, preset=preset, resource_dir=resource_dir)
    return PipelineCtx(slug=slug, params=params or {}, resources=bundle)


def build_preset(slug: str, preset: str | None = None, ctx: PipelineCtx | None = None,
                 resource_dir: Path | None = None) -> DomainPreset:
    """从 resources/<slug>/preset.json 或 presets/<name>.json 构建预设；缺失回落通用。"""
    if ctx is None:
        ctx = make_ctx(slug, resource_dir=resource_dir, preset=preset)
    cfg = ctx.resources.preset
    if cfg and cfg.get("stages"):
        return DomainPreset.from_dict(cfg, ctx)
    return default_preset(ctx)


def default_preset(ctx: PipelineCtx | None = None) -> DomainPreset:
    return DomainPreset("generic", "通用预设（无领域阶段，仅质量过滤）",
                        [QualityScoreStage("quality_score")])


def discover_presets(slug: str | None = None, resource_dir: Path | None = None) -> list[str]:
    """res目录下领域 slug；或指定 slug 时列出其命名预设名。无参时返回 slugs（向后兼容）。"""
    res = resource_dir or RESOURCE_DIR
    if not res.exists():
        return []
    if slug is not None:
        names = []
        dp = find_preset_config(slug, None, res)
        if dp:
            cfg = _load(dp) or {}
            names.append(cfg.get("name", "default"))
        pd_ = res / slug / "presets"
        if pd_.exists():
            for f in sorted(pd_.glob("*.json")):
                cfg = _load(f) or {}
                nm = cfg.get("name", f.stem)
                if nm not in names:
                    names.append(nm)
        return names
    return sorted(d.name for d in res.iterdir()
                  if d.is_dir() and ((d / "preset.json").exists() or (d / "presets").exists()))


def preset_options(slug: str, resource_dir: Path | None = None) -> list[tuple[str, str]]:
    """该领域可选预设（label, name）。"""
    res = resource_dir or RESOURCE_DIR
    out = []
    for nm in discover_presets(slug, res):
        p = find_preset_config(slug, nm, res)
        cfg = _load(p) if p else {}
        out.append((f"{cfg.get('description') or nm}({slug}/{nm})", nm))
    return out or [(f"{slug} 通用", None)]
