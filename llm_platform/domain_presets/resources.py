"""资源加载器：把 resources/<domain>/*.json（知识即数据）读入并预编译正则。

约定：目录结构见 resources/ 下。合并策略：_shared 为默认，领域文件覆盖同名表。
所有正则在此一次性编译并缓存，避免逐样本重复编译。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# llm_platform/domain_presets/resources.py -> parents[2] = 项目根
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESOURCE_DIR = PROJECT_ROOT / "resources"

TABLE_NAMES = ["deid", "sections", "terms", "units", "qc", "structure", "citation", "numeric", "options"]


def _load(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def find_preset_config(slug: str, preset: str | None,
                       resource_dir: Path | None = None) -> Path | None:
    """解析命名预设对应的文件（默认 <slug>/preset.json；否则 <slug>/presets/<name>.json，
    并按 config['name'] 回退，如 'medical_cn' 命中 preset.json）。"""
    res_dir = resource_dir or RESOURCE_DIR
    dom = res_dir / slug
    if preset in (None, "", "default"):
        for cand in (dom / "preset.json", dom / "presets" / "default.json"):
            if cand.exists():
                return cand
        return None
    cand = dom / "presets" / f"{preset}.json"
    if cand.exists():
        return cand
    for p in [dom / "preset.json"] + sorted((dom / "presets").glob("*.json")):
        cfg = _load(p)
        if cfg and cfg.get("name") == preset:
            return p
    return None


def compile_norm(table: dict | None, key: str = "normalize") -> list:
    """把 {<key>:[{pattern,replacement}]} 编译成 [(compiled_re, replacement), ...]"""
    if not table:
        return []
    out = []
    for item in table.get(key, []):
        try:
            out.append((re.compile(item["pattern"]), item["replacement"]))
        except re.error:
            continue
    return out


@dataclass
class ResourceBundle:
    slug: str
    rail: dict = field(default_factory=dict)

    def __post_init__(self):
        self.deid = self.rail.get("deid", {})
        self.sections = self.rail.get("sections", {})
        self.terms = self.rail.get("terms", {})
        self.units = self.rail.get("units", {})
        self.qc = self.rail.get("qc", {})
        self.structure = self.rail.get("structure", {})
        self.citation = self.rail.get("citation", {})
        self.numeric = self.rail.get("numeric", {})
        self.options = self.rail.get("options", {})
        self.preset = self.rail.get("preset", {})
        self._compile()

    # —— 以下为预编译产物 ——
    def _compile(self):
        # deid 组：普通/上下文锚定
        self.deid_groups: list = []
        for g in self.deid.get("pattern_groups", []):
            e = dict(g)
            if g.get("kind") == "name_heuristic":
                e["kind"] = "name_heuristic"
                self.deid_groups.append(e)
            elif g.get("context_anchor"):
                anchors = "|".join(re.escape(a) for a in g["context_anchor"])
                e["context_pat"] = re.compile(rf"({anchors})\s*[:：]?\s*({g['pattern']})")
                e["_enclosing"] = f"{g.get('replacement','')}"
                e["exclude"] = g.get("exclude", [])
                e["exclude_after"] = g.get("exclude_after", [])
                self.deid_groups.append(e)
            else:
                e["pat"] = re.compile(g["pattern"])
                self.deid_groups.append(e)
        self._whitelist = set(self.deid.get("whitelist", []))
        self._suffix_end = {x for x in self.deid.get("suffix_whitelist_endings", []) if x}
        self._guard = self.deid.get("overmatch_guard", {})

        # sections
        canon = self.sections.get("canonical", [])
        self.section_aliases = {c["name"]: c.get("aliases", []) for c in canon}
        self.alias_to_canonical = {}
        for c in canon:
            for a in c.get("aliases", []):
                self.alias_to_canonical[a] = c["name"]
        order = self.sections.get("order_index", [c["name"] for c in canon])
        self.order_index = order
        # 头部匹配：允许行内。前缀为非 CJK 边界（行首/句号/分号/空白），防止匹配长词内部；
        # 后跟可选括号或冒号（消费掉，正文从其后面开始）。
        aliases = sorted(self.alias_to_canonical.keys(), key=len, reverse=True)
        if aliases:
            alt = "|".join(re.escape(a) for a in aliases)
            try:
                self.section_re = re.compile(
                    rf"(?<![A-Za-z0-9一-龥])(?:【|\[|（|\s)*(?:{alt})(?:】|\]|）|\s|[:：])+\s*",
                    re.MULTILINE)
            except re.error:
                self.section_re = None
        else:
            self.section_re = None

        # terms
        self.term_typo = [(k, v) for k, v in self.terms.get("typo_fix", {}).items()]
        self.term_abbrev = []
        for abbr, full in self.terms.get("abbrev_to_full", {}).items():
            self.term_abbrev.append((re.compile(rf"(?<![A-Za-z]){re.escape(abbr)}(?![A-Za-z])"), full))
        self.term_latin = []
        for abbr, full in self.terms.get("latin_to_cn", {}).items():
            self.term_latin.append((re.compile(rf"(?<![A-Za-z0-9]){re.escape(abbr)}(?![A-Za-z0-9])"), full))
        self._preserve = list(self.terms.get("preserve", []))

        # units：别名->规范
        self.unit_rules = []
        for u in self.units.get("canonical", []):
            for a in u.get("aliases", []):
                try:
                    self.unit_rules.append(
                        (re.compile(rf"(?<!\w)(\d+(?:\.\d+)?\s*){re.escape(a)}(?!\w)"), rf"\1{u['replacement']}"))
                except re.error:
                    continue
        self.dose_rules = self.units.get("dose_rules", [])
        # lab_rules：化验值区间（units.json）
        self.lab_rules = []
        for r in self.units.get("lab_rules", []):
            try:
                self.lab_rules.append((r, re.compile(r["pattern"])))
            except re.error:
                continue

        # citation：文号/案号 keep（与 deid.kept_patterns 合并）与规范化
        self.citation_normalize = compile_norm(self.citation, key="canonicalize")
        kept = list(self.citation.get("kept_patterns", [])) + list(self.deid.get("kept_patterns", []))
        kept = [k for k in kept if k]
        self.citation_keep_re = (re.compile("|".join(sorted(kept, key=len, reverse=True)))
                                 if kept else None)

        # 法律：文档类型与层级定义（structure.json）
        self.doc_types = self.structure.get("doc_types", {})
        self.hierarchy = self.structure.get("hierarchy", {})

        # 通用 normalize 表（structure / numeric / options 共用形态）
        self.structure_norms = compile_norm(self.structure)
        self.numeric_norms = compile_norm(self.numeric)
        self.option_norms = compile_norm(self.options)

    # —— 供各阶段使用的便捷访问 ——
    def is_whitelisted(self, word: str) -> bool:
        return word in self._whitelist

    def ends_with_whitelisted_suffix(self, word: str) -> bool:
        return any(word.endswith(x) for x in self._suffix_end)

    def preserve(self, word: str) -> bool:
        return word in self._preserve

    def guard(self) -> dict:
        return self._guard

    def protected_spans(self, text: str) -> list:
        """案号/文号/日期/法院名等受保护区间（脱敏不得改写）。"""
        if not self.citation_keep_re:
            return []
        return [(m.start(), m.end()) for m in self.citation_keep_re.finditer(text)]

    def overlaps_protected(self, text: str, start: int, end: int) -> bool:
        for s, e in self.protected_spans(text):
            if start < e and end > s:
                return True
        return False

    def preserved_ranges(self, text: str) -> list:
        ranges = []
        for term in self._preserve:
            if not term:
                continue
            start = 0
            while True:
                i = text.find(term, start)
                if i == -1:
                    break
                ranges.append((i, i + len(term)))
                start = i + 1
        return ranges

    def overlaps_preserved(self, text: str, start: int, end: int) -> bool:
        for s, e in self.preserved_ranges(text):
            if start < e and end > s:
                return True
        return False


    @classmethod
    def load(cls, slug: str, preset: str | None = None,
             resource_dir: Path | None = None) -> "ResourceBundle":
        """加载 <slug>/ 与 _shared/，领域覆盖共享；preset 决定 preset.json / presets/<name>.json。
        缺失表回落共享，仍缺失则为空 dict；坏表带警告跳过（不整体失败）。
        """
        res_dir = resource_dir or RESOURCE_DIR
        shared = res_dir / "_shared"
        domain = res_dir / slug

        shared_merged: dict = {n: (_load(shared / f"{n}.json") or {}) for n in TABLE_NAMES}
        rail: dict = {}
        for name in TABLE_NAMES:
            tmp = _load(domain / f"{name}.json")
            # 仅当领域有该文件才覆盖；否则用共享；都没有则空 dict
            rail[name] = tmp if tmp is not None else shared_merged[name]

        # 解析命名预设（或默认 preset.json）
        cfg_path = find_preset_config(slug, preset, res_dir)
        config = _load(cfg_path) if cfg_path else {}
        if isinstance(config.get("qc"), dict):   # 预设级 qc 覆盖（浅覆盖）
            rail["qc"] = {**rail["qc"], **config["qc"]}

        bundle = cls(slug=slug, rail={**rail, "preset": config})
        bundle.preset = config or {}
        # 读取 _meta（schema_version 门控，仅提示）
        meta = _load(domain / "_meta.json")
        if meta and meta.get("schema_version", 1) > 1:
            print(f"[resources] {slug} 资源 schema_version={meta['schema_version']} 高于支持值，请核对")
        return bundle
