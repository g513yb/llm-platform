import json
import os
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT / "data/reference/medical/raw"
DST_DIR = ROOT / "data/reference/medical"
DST = DST_DIR / "cmb_train_alpaca.jsonl"

ANSWER_RE = re.compile(r"^[A-F]+$")
OPTION_KEYS = ["A", "B", "C", "D", "E", "F"]


def build_input(item):
    question = item["question"].strip()
    opt = item["option"]
    option_lines = []
    for k in OPTION_KEYS:
        if k in opt and opt[k] is not None:
            option_lines.append(f"{k}. {opt[k]}")
    return question + "\n" + "\n".join(option_lines)


def build_instruction(item):
    return (
        f"以下是中国{item['exam_type']}中{item['exam_class']}考试的一道"
        f"{item['question_type']}，请直接给出答案选项。"
    )


def main():
    data = []
    for fp in sorted(RAW_DIR.rglob("*.json")):
        if fp.name == "CMB-train-merge.json":
            continue
        with open(fp, "r", encoding="utf-8") as f:
            data.extend(json.load(f))

    os.makedirs(DST_DIR, exist_ok=True)
    stats = Counter()
    kept = 0
    dropped = []

    with open(DST, "w", encoding="utf-8") as out:
        for i, item in enumerate(data):
            stats["total"] += 1
            qt = item.get("question_type", "")
            ans = item.get("answer", "") or ""
            ans = ans.strip()

            if qt == "C型选择题":
                stats["drop_c_type"] += 1
                dropped.append((i, "c_type", ans))
                continue
            if not ans:
                stats["drop_empty_answer"] += 1
                dropped.append((i, "empty_answer", ans))
                continue
            if len(ans) > 6:
                stats["drop_long_answer"] += 1
                dropped.append((i, "long_answer", ans))
                continue
            if not ANSWER_RE.match(ans):
                stats["drop_non_letter_answer"] += 1
                dropped.append((i, "non_letter_answer", ans))
                continue

            opt = item["option"]
            present = {k: (opt[k] or "").strip() for k in OPTION_KEYS if k in opt}
            if present and all(not v for v in present.values()):
                stats["drop_all_options_empty"] += 1
                dropped.append((i, "all_options_empty", ans))
                continue
            if any(not present.get(c, "") for c in ans):
                stats["drop_answer_points_empty_option"] += 1
                dropped.append((i, "answer_points_empty_option", ans))
                continue

            rec = {
                "instruction": build_instruction(item),
                "input": build_input(item),
                "output": ans,
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            kept += 1
            stats["kept"] += 1

    print("=== 转换统计 ===")
    for k, v in stats.most_common():
        print(f"  {k}: {v}")
    print(f"保留 {kept} 条 -> {DST}")
    print(f"过滤 {stats['total'] - kept} 条")
    if dropped:
        print("\n=== 过滤样例（前 10）===")
        for i, reason, ans in dropped[:10]:
            print(f"  idx={i} reason={reason} answer={ans!r}")


if __name__ == "__main__":
    main()