"""输入归一化：Alpaca / ShareGPT / CSV → 内部 WorkItem(ShareGPT messages)。
纯文本出指令（raw-text instruction generation）为 P2，本模块留 seam。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from llm_platform.domain_presets.engine import WorkItem

P2_TXT_MSG = (
    "检测到纯文本(.txt)。本 Sprint 仅支持『已含 指令-输出对』的数据（Alpaca/ShareGPT/CSV）。\n"
    "从原始文本生成指令（raw-text instruction generation）是 P2 扩展点；reader 层已留"
    " `read_txt_raw()` 接口，后续接入即可。"
)


def read_inputs(paths: list[str], read_txt_raw: Optional[Callable] = None,
                ) -> tuple[list[WorkItem], dict]:
    files = [p for p in paths if p]
    items: list[WorkItem] = []
    skipped: dict = {}
    rid = 0
    for p in files:
        try:
            recs = _read_file(p, Path(p).suffix.lower(), read_txt_raw)
        except Exception as e:  # noqa: BLE001
            skipped[Path(p).name] = str(e)[:120]
            continue
        for raw in recs:
            try:
                items.append(_normalize(raw, f"{Path(p).name}#{rid}", rid))
                rid += 1
            except Exception as e:  # noqa: BLE001
                skipped[f"{Path(p).name}#{rid}"] = str(e)[:100]
                continue
    meta = {"files": len(files), "rows_loaded": len(items), "skipped": skipped}
    return items, meta


# ---------------------------------------------------------------- 文件读取
def _read_file(path: str, ext: str, read_txt_raw: Optional[Callable]) -> list:
    if ext == ".json":
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        return data if isinstance(data, list) else [data]
    if ext == ".jsonl":
        rows = []
        for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows
    if ext == ".csv":
        return _read_csv(path)
    if ext == ".txt":
        lines = [l for l in Path(path).read_text(encoding="utf-8-sig").splitlines() if l.strip()]
        if lines and all(_is_jsonl_line(l) for l in lines):
            return [json.loads(l) for l in lines]
        if read_txt_raw:
            return read_txt_raw(Path(path).read_text(encoding="utf-8-sig"))
        raise ValueError(P2_TXT_MSG)
    raise ValueError(f"不支持的文件类型：{ext}（支持 .json/.jsonl/.csv/.txt）")


def _is_jsonl_line(line: str) -> bool:
    try:
        json.loads(line)
        return True
    except Exception:
        return False


def _read_csv(path: str) -> list:
    df = None
    for enc in ("utf-8-sig", "gbk", "utf-8"):
        try:
            df = pd.read_csv(path, encoding=enc)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    if df is None:
        raise ValueError("CSV 解码失败（尝试 utf-8-sig/gbk/utf-8）")
    if df.empty:
        return []
    cols = {str(c).strip().lower(): c for c in df.columns}
    # ShareGPT 长表 (id, role, content)
    if "messages" in cols or ({"role", "content"} <= set(cols)):
        return _csv_long_to_messages(df, cols)
    # Alpaca 或中文列名
    if {"instruction", "output"} <= set(cols) or {"指令", "输出"} <= set(cols):
        return list(df.to_dict("records"))
    raise ValueError("CSV 需包含 instruction/input/output 列（或中文 指令/输入/输出，或 id/role/content）")


def _csv_long_to_messages(df, cols):
    id_col = cols.get("id") or cols.get("对话id") or df.columns[0]
    role_col = cols.get("role") or cols.get("角色")
    content_col = cols.get("content") or cols.get("内容")
    grouped: dict = {}
    for _, row in df.iterrows():
        gid = row[id_col]
        grouped.setdefault(gid, []).append({"role": str(row[role_col]).strip(),
                                            "content": str(row[content_col]).strip()})
    return [{"messages": v} for v in grouped.values()]


# ---------------------------------------------------------------- 归一化
def _normalize(raw, source: str, rid: int) -> WorkItem:
    if isinstance(raw, list):           # 直接嵌套 messages
        msgs = raw
    elif isinstance(raw, dict):
        if isinstance(raw.get("messages"), list):
            msgs = raw["messages"]
        elif "instruction" in raw or "output" in raw:
            user = str(raw.get("instruction", "")).strip()
            inp = str(raw.get("input") or "").strip()
            if inp:
                user = f"{user}\n\n{inp}"
            msgs = [{"role": "user", "content": user},
                    {"role": "assistant", "content": str(raw.get("output", "")).strip()}]
        elif "指令" in raw or "输出" in raw:
            user = str(raw.get("指令", "")).strip()
            inp = str(raw.get("输入") or "").strip()
            if inp:
                user = f"{user}\n\n{inp}"
            msgs = [{"role": "user", "content": user},
                    {"role": "assistant", "content": str(raw.get("输出", "")).strip()}]
        else:
            raise ValueError(f"{source}: 无法识别结构（需 Alpaca 或 ShareGPT）")
    else:
        raise ValueError(f"{source}: 期望 对象/数组，得到 {type(raw).__name__}")
    msgs = [{"role": m.get("role"), "content": str(m.get("content", "")).strip()}
            for m in msgs if isinstance(m, dict) and m.get("role") in ("user", "assistant")]
    return WorkItem(rid, source, msgs)
