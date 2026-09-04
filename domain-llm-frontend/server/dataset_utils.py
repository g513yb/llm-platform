import json
import os

import pandas as pd


def _normalize(sample):
    if not isinstance(sample, dict):
        return None
    if sample.get("text"):
        return {"text": str(sample["text"])}
    instruction = sample.get("instruction") or sample.get("prompt") or sample.get("question")
    output = sample.get("output") or sample.get("completion") or sample.get("answer") or sample.get("response")
    if instruction is None and output is None:
        instruction = sample.get("input")
        output = sample.get("label")
    if instruction is None or output is None:
        return None
    item = {"instruction": str(instruction), "output": str(output)}
    extra_input = sample.get("input")
    if extra_input and "instruction" in sample:
        item["input"] = str(extra_input)
    return item


def parse_dataset(path):
    ext = os.path.splitext(path)[1].lower()
    raw = []
    if ext == ".jsonl":
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    raw.append(json.loads(line))
    elif ext == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = data.get("data") or data.get("train") or data.get("samples") or []
        raw = list(data)
    elif ext == ".csv":
        df = pd.read_csv(path)
        raw = df.to_dict(orient="records")
    elif ext == ".txt":
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                if "\t" in line:
                    q, a = line.split("\t", 1)
                    raw.append({"instruction": q, "output": a})
                else:
                    raw.append({"text": line})
    else:
        raise ValueError(f"不支持的数据集格式：{ext}（支持 csv/txt/json/jsonl）")

    samples = []
    for s in raw:
        item = _normalize(s)
        if item:
            samples.append(item)
    if not samples:
        raise ValueError("未解析到有效样本，请确认字段包含 instruction/output（或 prompt/completion、question/answer、text）")
    return samples