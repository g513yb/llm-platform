"""落盘：ShareGPT jsonl/.json + <slug>_config.json（可复现）。"""
from __future__ import annotations

import json
import os
from pathlib import Path

from llm_platform.domain_presets.engine import WorkItem

# llm_platform/data_pipeline/io.py -> parents[2] = 项目根
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def ensure_dir(dir_path: Path | None = None) -> None:
    os.makedirs(dir_path or DATA_DIR, exist_ok=True)


def write_outputs(kept_items: list[WorkItem], slug: str, params: dict, meta: dict) -> list[str]:
    ensure_dir()
    stem = DATA_DIR / f"{slug}_sharegpt"
    jsonl_path = f"{stem}.jsonl"
    json_path = f"{stem}.json"
    config_path = str(DATA_DIR / f"{slug}_config.json")

    rows = [{"messages": it.messages, "source": it.source} for it in kept_items]
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({"domain": slug, "params": params, "meta": meta,
                   "counts": {"kept": len(kept_items)}}, f, ensure_ascii=False, indent=2)
    return [jsonl_path, json_path, config_path]
