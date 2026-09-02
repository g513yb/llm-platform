"""领域预设引擎：可复用的阶段化处理器。

核心抽象：
- WorkItem    单个样本（一条指令-微调对话，ShareGPT messages）。
- Issue       记录某阶段为何清洗/标注/警告/丢弃。
- Stage       可插拔处理器（改写内容 / 增删拆分消息 / 写 meta / 发 issue）。
- DomainPreset 有序 stage 列表，由 resources/<domain>/preset.json 数据驱动。
- PipelineCtx 一次构建：已编译资源 + 运行参数 + 阶段统计。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Issue:
    stage: str
    code: str
    level: str          # cleaned | annotated | warning | drop
    message: str
    start: Optional[int] = None
    end: Optional[int] = None
    detail: Optional[dict] = None


@dataclass
class WorkItem:
    record_id: int
    source: str                    # alpaca | sharegpt | csv | sample
    messages: list                 # [{"role","content"}, ...] ShareGPT 形态
    meta: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)
    status: str = "pending"        # pending | kept | dropped
    drop_reason: Optional[str] = None

    def user_turns(self) -> list:
        return [m for m in self.messages if m.get("role") == "user"]

    def assistant_turns(self) -> list:
        return [m for m in self.messages if m.get("role") == "assistant"]

    def all_text(self) -> str:
        return "\n".join(str(m.get("content", "")) for m in self.messages)


@dataclass
class StageStats:
    issue_ctr: dict = field(default_factory=dict)      # stage -> issue 数
    cleaned_ctr: dict = field(default_factory=dict)    # stage -> cleaned 改写数

    def record(self, stage: str, issues: list) -> None:
        if not issues:
            return
        self.issue_ctr[stage] = self.issue_ctr.get(stage, 0) + len(issues)
        if any(i.level == "cleaned" for i in issues):
            self.cleaned_ctr[stage] = self.cleaned_ctr.get(stage, 0) + 1


class Stage:
    """基类：子类实现 run()。可 (a)改写 content (b)增/并/拆 messages (c)写 meta (d)发 issues。"""

    def __init__(self, name: str, params: Optional[dict] = None, enabled: bool = True):
        self.name = name
        self.params = params or {}
        self.enabled = enabled

    def run(self, item: WorkItem, ctx: "PipelineCtx") -> tuple[WorkItem, list[Issue]]:
        raise NotImplementedError


@dataclass
class PipelineCtx:
    slug: str
    params: dict
    resources: Any = None            # ResourceBundle
    stats: StageStats = field(default_factory=StageStats)
    scratch: dict = field(default_factory=dict)


class DomainPreset:
    def __init__(self, name: str, description: str, stages: list[Stage]):
        self.name = name
        self.description = description
        self.stages = stages

    @classmethod
    def from_dict(cls, cfg: dict, ctx: PipelineCtx) -> "DomainPreset":
        from . import make_stage           # 避免循环导入
        stages = [make_stage(s["kind"], s.get("params", {})) for s in cfg.get("stages", [])]
        return cls(name=cfg.get("name", "generic"), description=cfg.get("description", ""), stages=stages)

    def run(self, item: WorkItem, ctx: PipelineCtx) -> WorkItem:
        for stage in self.stages:
            if not stage.enabled:
                continue
            item, issues = stage.run(item, ctx)
            item.issues.extend(issues)
            ctx.stats.record(stage.name, issues)
        return item
