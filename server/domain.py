"""领域注册表：从 config 读取，供 UI 与后续服务统一使用。"""
from config import DOMAINS, DOMAIN_SLUGS

_TABLE = {label: desc for label, desc in DOMAINS}


def labels():
    return [d[0] for d in DOMAINS]


def describe(label):
    return _TABLE.get(label, "")


def slug(label):
    """中文领域标签 -> slug（如 医疗 -> medical）。未知标签回落 generic。"""
    return DOMAIN_SLUGS.get(label, "generic")
