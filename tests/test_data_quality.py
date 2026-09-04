"""数据质量测试：从 6 种代码分支各选代表数据源，抽 50 条经 data_pipeline 处理，保存输入与输出。

分支覆盖：
  1. _parse_clin          — CMB-Clin（病例问答）
  2. _parse_mcq           — CMMLU（选择题 A/B/C/D 字段）
  3. _parse_qa→Alpaca     — FinGPT（instruction+output）
  4. _parse_qa→LawBench   — LawBench（instruction+question+answer）
  5. _parse_qa→DISC-Law   — DISC-Law-Triplet（input+output+reference）
  6. _parse_qa→兜底        — CrimeKG（question+answers[]）
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "server"))

from data_pipeline.readers import _iter_records, read_all
from data_pipeline.io import messages_to_alpaca

DOWNLOADS = PROJECT_ROOT / "tests" / "fixtures" / "_downloads"
OUTPUT_DIR = PROJECT_ROOT / "tests" / "eval_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SOURCES = [
    {
        "name": "01_cmb_clin",
        "branch": "_parse_clin",
        "domain": "医疗",
        "path": DOWNLOADS / "cmb-hf" / "CMB-Clin-qa.json",
        "desc": "CMB-Clin 病例问答（description+QA_pairs）",
    },
    {
        "name": "02_cmmlu_mcq",
        "branch": "_parse_mcq",
        "domain": "教育",
        "path": DOWNLOADS / "cmmlu" / "data" / "test" / "agronomy.csv",
        "desc": "CMMLU 选择题（question+A/B/C/D+answer）",
    },
    {
        "name": "03_fingpt_alpaca",
        "branch": "_parse_qa_alpaca",
        "domain": "金融",
        "path": DOWNLOADS / "fingpt" / "data" / "train-00000-of-00001-dabab110260ac909.parquet",
        "desc": "FinGPT 金融情感（instruction+output Alpaca）",
    },
    {
        "name": "04_lawbench",
        "branch": "_parse_qa_lawbench",
        "domain": "法律",
        "path": DOWNLOADS / "lawbench" / "data" / "zero_shot" / "2-1.json",
        "desc": "LawBench 法律基准（instruction+question+answer）",
    },
    {
        "name": "05_disc_law_triplet",
        "branch": "_parse_qa_disc_law",
        "domain": "法律",
        "path": DOWNLOADS / "disc-law" / "DISC-Law-SFT-Triplet-QA-released.jsonl",
        "desc": "DISC-Law Triplet（reference+input+output）",
    },
    {
        "name": "06_crimekg_qa",
        "branch": "_parse_qa_fallback",
        "domain": "法律",
        "path": DOWNLOADS / "crimekg" / "data" / "qa_corpus.json" / "qa_corpus.json",
        "desc": "CrimeKG 法律问答（question+answers[]）",
    },
]

N = 50


def extract_records(path: Path, n: int) -> list[dict]:
    """从数据文件读取前 n 条原始记录。"""
    recs = []
    for rec in _iter_records(path):
        recs.append(rec)
        if len(recs) >= n:
            break
    return recs


def save_jsonl(path: Path, rows: list) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")


def run_one(src: dict) -> dict:
    name = src["name"]
    path = src["path"]

    if not path.exists():
        return {"name": name, "error": f"文件不存在: {path}"}

    recs = extract_records(path, N)
    if not recs:
        return {"name": name, "error": "未能读取任何记录"}

    save_jsonl(OUTPUT_DIR / f"{name}_input.jsonl", recs)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as tmp:
        for r in recs:
            tmp.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
        tmp_path = tmp.name

    try:
        items, dropped, counts = read_all([tmp_path])
    finally:
        os.unlink(tmp_path)

    output_rows = [messages_to_alpaca(msgs) for msgs in items]

    save_jsonl(OUTPUT_DIR / f"{name}_output.jsonl", output_rows)

    return {
        "name": name,
        "branch": src["branch"],
        "domain": src["domain"],
        "desc": src["desc"],
        "input_count": len(recs),
        "kept": len(items),
        "dropped": dropped,
        "type_counts": counts,
        "output_file": str(OUTPUT_DIR / f"{name}_output.jsonl"),
    }


def main():
    results = []
    for src in SOURCES:
        print(f"处理: {src['name']} — {src['desc']}")
        r = run_one(src)
        results.append(r)
        if "error" in r:
            print(f"  错误: {r['error']}")
        else:
            print(
                f"  输入{r['input_count']}条 → 保留{r['kept']} 丢弃{r['dropped']} "
                f"类型{r['type_counts']}"
            )

    summary_path = OUTPUT_DIR / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n汇总写入 {summary_path}")


if __name__ == "__main__":
    main()