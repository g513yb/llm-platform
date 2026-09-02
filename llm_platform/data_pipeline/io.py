"""落盘：训练数据统一为 Alpaca({instruction,input,output})（可切回 ShareGPT）+ <slug>_config.json（可复现）。
内部 WorkItem.messages 不变；仅在落盘时转换输出格式。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from config import OUTPUT_FORMAT
from llm_platform.domain_presets.engine import WorkItem

# llm_platform/data_pipeline/io.py -> parents[2] = 项目根
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def ensure_dir(dir_path: Path | None = None) -> None:
    os.makedirs(dir_path or DATA_DIR, exist_ok=True)


def messages_to_alpaca(messages: list) -> dict:
    """把 messages 转成 Alpaca {instruction,input,output}。
    默认单轮：instruction=首个 user，output=末个 assistant，input="".
    多轮（messages>2）：把首轮之后的轮次拼进 input 作背景，末轮 assistant 为 output。
    """
    users = [m.get("content") for m in messages if m.get("role") == "user" and m.get("content")]
    assts = [m.get("content") for m in messages if m.get("role") == "assistant" and m.get("content")]
    instruction = users[0] if users else ""
    output = assts[-1] if assts else ""
    input_ = ""
    if len(messages) > 2 and users:
        ctx = [m.get("content") for m in messages[1:] if m.get("content")]
        input_ = "\n".join(ctx)
    return {"instruction": instruction, "input": input_, "output": output}


def _rows_for_format(kept_items: list, fmt: str) -> list:
    if fmt == "sharegpt":
        return [{"messages": it.messages, "source": it.source} for it in kept_items]
    return [dict(messages_to_alpaca(it.messages), source=it.source) for it in kept_items]


def write_outputs(kept_items: list[WorkItem], slug: str, params: dict, meta: dict) -> list[str]:
    ensure_dir()
    fmt = OUTPUT_FORMAT
    rows = _rows_for_format(kept_items, fmt)
    name = "alpaca" if fmt == "alpaca" else "sharegpt"
    stem = DATA_DIR / f"{slug}_{name}"
    jsonl_path = f"{stem}.jsonl"
    json_path = f"{stem}.json"
    config_path = str(DATA_DIR / f"{slug}_config.json")

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({"domain": slug, "params": params, "meta": meta,
                   "format": fmt, "counts": {"kept": len(kept_items)}},
                  f, ensure_ascii=False, indent=2)
    return [jsonl_path, json_path, config_path]
