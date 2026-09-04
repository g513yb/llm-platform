"""输入输出：messages -> Alpaca 落盘。

Alpaca 格式：{instruction, input, output}，PEFT 微调主流形态。
内部 messages = [{role, content}, ...] 是引擎契约（与对话 Tab 一致）。
"""
from __future__ import annotations

import json

from config import DATA_DIR


def messages_to_alpaca(messages: list[dict]) -> dict:
    """[user, assistant] -> {instruction, input, output}。"""
    user = next((m["content"] for m in messages if m["role"] == "user"), "")
    asst = next((m["content"] for m in messages if m["role"] == "assistant"), "")
    return {"instruction": user, "input": "", "output": asst}


def write_outputs(items: list[list[dict]], slug: str) -> list[str]:
    """把 messages 列表落盘 Alpaca jsonl，返回输出文件路径列表。"""
    if not items:
        return []
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{slug}_alpaca.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for m in items:
            f.write(json.dumps(messages_to_alpaca(m), ensure_ascii=False) + "\n")
    return [str(path)]
