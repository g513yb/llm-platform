"""领域注册表：从 config 读取，供 UI 与后续服务统一使用。"""
from config import DOMAINS, DOMAIN_SLUGS

_TABLE = {label: desc for label, desc in DOMAINS}


def labels():
    return [d[0] for d in DOMAINS]


def describe(label):
    return _TABLE.get(label, "")


def slug(label):
    """中文领域标签 -> 资源目录 slug（如 医疗 -> medical）。未知标签回落通用。"""
    return DOMAIN_SLUGS.get(label, "generic")


def default_preset_name(label):
    """该领域默认预设名（资源目录下 preset.json 的 name，缺失则用 '通用'）。"""
    return slug(label) if slug(label) in DOMAIN_SLUGS.values() else "通用"
