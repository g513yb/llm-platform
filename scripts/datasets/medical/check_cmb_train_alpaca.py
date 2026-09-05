import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT / "data/reference/medical/raw"
DST = ROOT / "data/reference/medical/cmb_train_alpaca.jsonl"

ANSWER_RE = re.compile(r"^[A-F]+$")
INSTR_RE = re.compile(r"^以下是中国.+中.+考试的一道.+，请直接给出答案选项。$")
OPTION_LINE_RE = re.compile(r"^([A-F])\.")
OPTION_KEYS = ["A", "B", "C", "D", "E", "F"]


def expected_record(item):
    qt = item.get("question_type", "")
    ans = (item.get("answer", "") or "").strip()
    if qt == "C型选择题" or not ans or len(ans) > 6 or not ANSWER_RE.match(ans):
        return None
    opt = item["option"]
    present = {k: (opt[k] or "").strip() for k in OPTION_KEYS if k in opt}
    if present and all(not v for v in present.values()):
        return None
    if any(not present.get(c, "") for c in ans):
        return None
    option_lines = []
    for k in OPTION_KEYS:
        if k in opt and opt[k] is not None:
            option_lines.append(f"{k}. {opt[k]}")
    instr = (
        f"以下是中国{item['exam_type']}中{item['exam_class']}考试的一道"
        f"{item['question_type']}，请直接给出答案选项。"
    )
    inp = item["question"].strip() + "\n" + "\n".join(option_lines)
    return {"instruction": instr, "input": inp, "output": ans}


def main():
    src = []
    for fp in sorted(RAW_DIR.rglob("*.json")):
        if fp.name == "CMB-train-merge.json":
            continue
        with open(fp, "r", encoding="utf-8") as f:
            src.extend(json.load(f))
    with open(DST, "r", encoding="utf-8") as f:
        lines = f.readlines()

    print(f"源数据 {len(src)} 条，产物 {len(lines)} 行\n")

    issues = Counter()
    input_lens = []
    output_lens = Counter()
    instr_set = set()
    seen = set()
    dup_count = 0
    empty_option_records = 0
    all_options_empty = 0
    answer_points_empty = 0
    unsorted_multi = 0

    for line in lines:
        try:
            rec = json.loads(line)
        except Exception:
            issues["json_parse_error"] += 1
            continue
        if set(rec.keys()) != {"instruction", "input", "output"}:
            issues["field_count_mismatch"] += 1
            continue
        instr, inp, out = rec["instruction"], rec["input"], rec["output"]
        if not instr or not inp or not out:
            issues["empty_field"] += 1
            continue
        if not INSTR_RE.match(instr):
            issues["instruction_template_mismatch"] += 1
        if not ANSWER_RE.match(out):
            issues["output_not_letter"] += 1
        if len(out) > 6:
            issues["output_too_long"] += 1
        output_lens[len(out)] += 1

        opt_map = {}
        for l in inp.split("\n")[1:]:
            m = OPTION_LINE_RE.match(l)
            if m:
                opt_map[m.group(1)] = l[3:].strip()
        opt_letters = list(opt_map.keys())
        if not opt_letters:
            issues["no_option_in_input"] += 1
        else:
            if opt_letters != OPTION_KEYS[: len(opt_letters)]:
                issues["option_not_contiguous"] += 1
            for c in out:
                if c not in opt_letters:
                    issues["answer_not_in_options"] += 1
                    break
            empty_opts = [k for k, v in opt_map.items() if not v]
            if empty_opts:
                empty_option_records += 1
                if len(empty_opts) == len(opt_map):
                    all_options_empty += 1
                if any(c in empty_opts for c in out):
                    answer_points_empty += 1

        if len(out) > 1 and list(out) != sorted(out):
            unsorted_multi += 1

        ilen = len(inp)
        input_lens.append(ilen)
        if ilen < 10:
            issues["input_too_short"] += 1
        if ilen > 4000:
            issues["input_too_long"] += 1

        instr_set.add(instr)
        sig = (instr, inp, out)
        if sig in seen:
            dup_count += 1
            issues["duplicate_record"] += 1
        else:
            seen.add(sig)

    print("=== 1. 格式与字段 ===")
    print(f"  JSON 解析失败: {issues['json_parse_error']}")
    print(f"  字段数不匹配: {issues['field_count_mismatch']}")
    print(f"  空字段: {issues['empty_field']}")
    print(f"  instruction 模板不匹配: {issues['instruction_template_mismatch']}")
    print(f"  distinct instruction 模板数: {len(instr_set)}")

    print("\n=== 2. output 合法性 ===")
    print(f"  output 非字母: {issues['output_not_letter']}")
    print(f"  output 过长: {issues['output_too_long']}")
    print(f"  output 长度分布(前10): {output_lens.most_common(10)}")
    print(f"  多选未按字母序: {unsorted_multi}")

    print("\n=== 3. input 选项完整性 ===")
    print(f"  无选项行: {issues['no_option_in_input']}")
    print(f"  选项不连续(A起): {issues['option_not_contiguous']}")
    print(f"  答案字母不在选项中: {issues['answer_not_in_options']}")

    print("\n=== 4. 空选项内容（原始数据特征，非错误）===")
    print(f"  至少一个选项内容为空: {empty_option_records}")
    print(f"  全部选项内容为空: {all_options_empty} (应为0)")
    print(f"  答案指向空选项: {answer_points_empty} (应为0)")

    print("\n=== 5. 长度异常 ===")
    print(f"  input 过短(<10): {issues['input_too_short']}")
    print(f"  input 过长(>4000): {issues['input_too_long']}")
    if input_lens:
        input_lens.sort()
        n = len(input_lens)
        print(f"  input 长度 min/median/max: {input_lens[0]}/{input_lens[n//2]}/{input_lens[-1]}")
        print(f"  input 长度 P95/P99: {input_lens[int(n*0.95)]}/{input_lens[int(n*0.99)]}")

    print("\n=== 6. 重复记录 ===")
    print(f"  完全重复行: {dup_count}")

    print("\n=== 7. 与源数据一致性（逐条对照）===")
    exp_records = [r for r in (expected_record(item) for item in src) if r]
    mismatch = 0
    if len(exp_records) != len(lines):
        print(f"  数量不一致: 期望 {len(exp_records)} vs 实际 {len(lines)}")
    for exp, act in zip(exp_records, lines):
        rec = json.loads(act)
        if exp != rec:
            mismatch += 1
            if mismatch <= 3:
                print(f"  不一致: 期望 {json.dumps(exp,ensure_ascii=False)[:150]}")
                print(f"         实际 {json.dumps(rec,ensure_ascii=False)[:150]}")
    print(f"  对照完成: {len(exp_records)} 条，不一致 {mismatch} 条")

    total_issues = sum(issues.values()) + all_options_empty + answer_points_empty + mismatch
    print(f"\n=== 总计问题数: {total_issues} ===")
    if total_issues == 0 and dup_count == 0:
        print("✓ 质量验证通过")
    else:
        print("✗ 存在问题，请检查上方明细")


if __name__ == "__main__":
    main()
