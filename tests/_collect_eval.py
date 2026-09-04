"""收集真实数据 pipeline 测试输出，抽样写到 tests/eval_input.json。跳过非真实数据用例。"""
import json, tempfile, pathlib, sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from llm_platform.data_pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"

cases = [
    ("医疗", "cmb_exam_medical.jsonl", "medical_qa", "test_cmb_exam_medical_qa_kept"),
    ("医疗", "cmb_clin_medical.jsonl", "medical_qa", "test_cmb_clin_medical_qa_kept"),
    ("医疗", "toyhom_medical.csv", "medical_qa", "test_toyhom_medical_qa_kept"),
    ("医疗", "huatuo_medical.jsonl", "medical_qa", "test_huatuo_medical_qa_kept"),
    ("医疗", "raw_medical.txt", "medical_cn", "test_raw_medical_medical_cn_kept"),
    ("医疗", "cmb_clin_medical.jsonl", "medical_cn", "test_cmb_clin_medical_cn_dropped"),
    ("医疗", "cmb_clin_medical_cn_bad.jsonl", "medical_cn", "test_cmb_clin_bad_medical_cn_dropped"),
    ("法律", "lawbench_qa_legal.jsonl", "legal_qa", "test_lawbench_qa_legal_qa_kept"),
    ("法律", "lawbench_qa_legal.jsonl", "legal_cn", "test_lawbench_qa_legal_cn_dropped"),
    ("法律", "disc_law_legal.jsonl", "legal_qa", "test_disc_law_legal_qa_kept"),
    ("法律", "raw_legal_judgment.txt", "legal_cn", "test_raw_legal_judgment_legal_cn_kept"),
    ("法律", "raw_legal_judgment_cn_bad.txt", "legal_cn", "test_raw_legal_judgment_bad_cn_dropped"),
    ("金融", "fingpt_finance.jsonl", "finance_qa", "test_fingpt_finance_qa_kept"),
    ("金融", "fingpt_finance.jsonl", "finance_cn", "test_fingpt_finance_cn_dropped"),
    ("金融", "fingpt_finance_cn_bad.jsonl", "finance_cn", "test_fingpt_cn_bad_dropped"),
    ("教育", "mmlu_education.csv", "education_cn", "test_mmlu_cn_kept"),
    ("教育", "cmmlu_education.csv", "education_cn", "test_cmmlu_cn_kept"),
]

results = []
for domain, fname, preset, test_id in cases:
    kw = {"max_len": 30000} if "judgment" in fname else {}
    with tempfile.TemporaryDirectory() as td:
        with mock.patch("llm_platform.data_pipeline.io.DATA_DIR", Path(td)):
            s = run_pipeline(domain, file_paths=[str(FIX / fname)], preset=preset, **kw)
        rows = []
        for p in Path(td).rglob("*_alpaca.jsonl"):
            for line in p.read_text(encoding="utf-8").splitlines():
                rows.append(json.loads(line))
    n = len(rows)
    if n <= 5:
        sample_idx = list(range(n))
    else:
        sample_idx = [0, n//4, n//2, 3*n//4, n-1]
    samples = []
    for i in sample_idx:
        r = rows[i]
        samples.append({
            "idx": i + 1,
            "instruction": r["instruction"][:300],
            "input": r["input"][:300] if r["input"] else "",
            "output": r["output"][:300],
        })
    results.append({
        "test_id": test_id, "domain": domain, "fixture": fname, "preset": preset,
        "total": s.total, "kept": s.kept, "dropped": s.dropped,
        "drop_reasons": list(s.drop_reasons.keys()) if s.drop_reasons else [],
        "output_rows": n, "samples": samples,
    })
    print(f"{test_id}: total={s.total} kept={s.kept} dropped={s.dropped} output={n}")

out_path = ROOT / "tests" / "eval_input.json"
out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n写到 {out_path}，{len(results)} 个用例")