"""验证所有 SCHEMAS 中支持的数据集都能被正确识别。

两类测试：
1. 单元测试（TestParse*）：用合成数据测试每个 _parse_* 函数的解析逻辑
2. 集成测试（test_real_data_*）：用 tests/fixtures/_downloads/ 下的真实数据测试 inspect/run_pipeline
3. 合成 fixture 测试（TestSyntheticData）：用 tests/fixtures/synthetic/ 下的合成数据测试 MedQA/CMMLU

运行：pytest tests/test_readers.py -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from data_pipeline import SUPPORTED, inspect, run_pipeline, SCHEMAS
from data_pipeline.readers import (
    _parse_clin, _parse_mcq, _parse_qa, _to_messages,
)

SYNTH = Path(__file__).parent / "fixtures" / "synthetic"
DL = Path(__file__).parent / "fixtures" / "_downloads"


# ========== 单元测试：_parse_mcq ==========

class TestParseMcq:
    """选择题解析：CMB-Exam / MedQA / CMMLU-MMLU / FinEval 四种 schema。"""

    def test_cmb_exam_option_dict(self):
        rec = {
            "question": "下列哪种药物是利尿剂？",
            "option": {"A": "呋塞米", "B": "美托洛尔", "C": "硝苯地平", "D": "卡托普利"},
            "answer": "A",
        }
        parsed = _parse_mcq(rec)
        assert parsed is not None
        q, opts, letter, expl = parsed
        assert "利尿剂" in q
        assert opts == {"A": "呋塞米", "B": "美托洛尔", "C": "硝苯地平", "D": "卡托普利"}
        assert letter == "A"
        assert expl == ""

    def test_medqa_options_dict_with_explanation(self):
        rec = {
            "question": "急性心梗最早期心电图改变？",
            "options": {"A": "Q波", "B": "ST抬高", "C": "T波倒置", "D": "ST压低"},
            "answer_idx": "B",
            "answer": "ST段抬高是急性心肌梗死最早期的心电图改变。",
        }
        parsed = _parse_mcq(rec)
        assert parsed is not None
        q, opts, letter, expl = parsed
        assert letter == "B"
        assert "ST段抬高" in expl

    def test_cmmlu_single_letter_fields(self):
        rec = {
            "question": "下列哪项不是高血压危险因素？",
            "A": "吸烟", "B": "高血脂", "C": "规律运动", "D": "男性年龄>55岁",
            "answer": "C",
        }
        parsed = _parse_mcq(rec)
        assert parsed is not None
        q, opts, letter, expl = parsed
        assert opts["C"] == "规律运动"
        assert letter == "C"

    def test_fineval_with_explanation(self):
        rec = {
            "id": 1,
            "question": "国际清偿力不包括一国的____。",
            "A": "自有储备", "B": "借入储备", "C": "在IMF的储备头寸", "D": "特别提款权",
            "answer": "B",
            "explanation": "国际清偿力=自有储备+借入储备。",
        }
        parsed = _parse_mcq(rec)
        assert parsed is not None
        q, opts, letter, expl = parsed
        assert letter == "B"
        assert "国际清偿力" in expl

    def test_no_question_returns_none(self):
        assert _parse_mcq({"A": "x", "B": "y", "answer": "A"}) is None

    def test_no_options_returns_none(self):
        assert _parse_mcq({"question": "test", "answer": "A"}) is None

    def test_no_valid_answer_returns_none(self):
        rec = {"question": "test", "option": {"A": "x", "B": "y"}, "answer": "Z"}
        assert _parse_mcq(rec) is None

    def test_to_messages_format(self):
        msgs = _to_messages("问题", {"A": "选项A", "B": "选项B"}, "A", "解析说明")
        assert msgs[0]["role"] == "user"
        assert "问题" in msgs[0]["content"]
        assert "A. 选项A" in msgs[0]["content"]
        assert msgs[1]["role"] == "assistant"
        assert "A. 选项A" in msgs[1]["content"]
        assert "解析：解析说明" in msgs[1]["content"]


# ========== 单元测试：_parse_clin ==========

class TestParseClin:
    """病例问答解析：CMB-Clin schema。"""

    def test_basic_clin(self):
        rec = {
            "id": 1, "title": "高血压病例",
            "description": "患者男，55岁，血压160/100mmHg",
            "QA_pairs": [
                {"question": "该患者的诊断？", "answer": "高血压2级"},
                {"question": "首选药物？", "answer": "ACEI类"},
            ],
        }
        result = _parse_clin(rec)
        assert len(result) == 2
        assert result[0][1]["content"] == "高血压2级"
        assert "病历" in result[0][0]["content"]

    def test_solution_fallback(self):
        rec = {"description": "病例", "QA_pairs": [{"question": "q", "solution": "通过solution回答"}]}
        result = _parse_clin(rec)
        assert len(result) == 1
        assert result[0][1]["content"] == "通过solution回答"

    def test_no_description_returns_empty(self):
        assert _parse_clin({"QA_pairs": [{"question": "q", "answer": "a"}]}) == []

    def test_no_qa_pairs_returns_empty(self):
        assert _parse_clin({"description": "desc"}) == []


# ========== 单元测试：_parse_qa ==========

class TestParseQa:
    """问答解析：Alpaca / LawBench / DISC-Law / CrimeKG / Huatuo / Toyhom。"""

    def test_alpaca_fingpt(self):
        rec = {"instruction": "What is the sentiment?", "input": "Strong earnings.", "output": "positive"}
        msgs = _parse_qa(rec)
        assert msgs is not None
        assert "sentiment" in msgs[0]["content"]
        assert msgs[1]["content"] == "positive"

    def test_alpaca_no_input(self):
        rec = {"instruction": "指令", "input": "", "output": "结果"}
        msgs = _parse_qa(rec)
        assert msgs[0]["content"] == "指令"

    def test_lawbench(self):
        rec = {"instruction": "请回答：", "question": "醉驾是否入刑？", "answer": "已入刑。"}
        msgs = _parse_qa(rec)
        assert msgs is not None
        assert "请回答" in msgs[0]["content"]
        assert "醉驾是否入刑" in msgs[0]["content"]
        assert msgs[1]["content"] == "已入刑。"

    def test_disc_law_pair(self):
        rec = {"id": 1, "input": "案件摘要", "output": "判决结果"}
        msgs = _parse_qa(rec)
        assert msgs[0]["content"] == "案件摘要"
        assert msgs[1]["content"] == "判决结果"

    def test_disc_law_triplet_with_reference(self):
        rec = {"id": 1, "reference": ["刑法第二百六十四条"], "input": "被告人盗窃", "output": "构成盗窃罪"}
        msgs = _parse_qa(rec)
        assert "参考法条" in msgs[0]["content"]
        assert "刑法第二百六十四条" in msgs[0]["content"]

    def test_disc_law_triplet_reference_already_in_input(self):
        rec = {"reference": ["刑法第二百六十四条"], "input": "根据刑法第二百六十四条，被告人盗窃", "output": "盗窃罪"}
        msgs = _parse_qa(rec)
        assert "参考法条" not in msgs[0]["content"]

    def test_crimekg(self):
        rec = {"_id": {"$oid": "x"}, "question": "正当防卫？", "answers": ["正当防卫是指..."], "category": "刑法"}
        msgs = _parse_qa(rec)
        assert "正当防卫" in msgs[0]["content"]
        assert "正当防卫是指" in msgs[1]["content"]

    def test_huatuo(self):
        rec = {"question": "能吃党参吗？", "response": "可以口服。"}
        msgs = _parse_qa(rec)
        assert msgs[0]["content"] == "能吃党参吗？"
        assert msgs[1]["content"] == "可以口服。"

    def test_toyhom(self):
        rec = {"department": "心血管科", "title": "高血压", "ask": "能吃党参吗？", "answer": "可以口服。"}
        msgs = _parse_qa(rec)
        assert msgs[0]["content"] == "能吃党参吗？"
        assert msgs[1]["content"] == "可以口服。"

    def test_empty_record_returns_none(self):
        assert _parse_qa({}) is None

    def test_priority_alpaca_over_lawbench(self):
        rec = {"instruction": "指令", "input": "输入", "output": "输出", "question": "问题", "answer": "回答"}
        msgs = _parse_qa(rec)
        assert msgs[1]["content"] == "输出"


# ========== 合成 fixture 测试 ==========

class TestSyntheticData:
    """合成 fixture：MedQA（jsonl）和 CMMLU（csv）。"""

    def test_medqa_jsonl(self):
        s, err = inspect("医疗", [str(SYNTH / "medqa.jsonl")])
        assert s is not None and err == "", err
        assert s.type_counts.get("选择题") == 3

    def test_cmmlu_csv(self):
        s, err = inspect("医疗", [str(SYNTH / "cmmlu.csv")])
        assert s is not None and err == "", err
        assert s.type_counts.get("选择题") == 4

    def test_medqa_run_pipeline(self, tmp_path):
        import llm_platform.data_pipeline.io as io_mod
        io_mod.DATA_DIR = tmp_path
        res = run_pipeline("医疗", [str(SYNTH / "medqa.jsonl")])
        assert res.kept == 3
        lines = (tmp_path / "medical_alpaca.jsonl").read_text(encoding="utf-8").strip().split("\n")
        assert set(json.loads(lines[0])) == {"instruction", "input", "output"}


# ========== 真实数据集成测试 ==========

REAL_FILES = {
    "CMB-Exam": ("cmb_unzipped/CMB/CMB-Exam/CMB-train/CMB-train-merge.json", "选择题"),
    "CMB-Clin": ("cmb_unzipped/CMB/CMB-Clin/CMB-Clin-qa.json", "病例问答"),
    "CrimeKG": ("crimekg/data/qa_corpus.json/qa_corpus.json", "问答"),
    "DISC-Law-Pair": ("disc-law/DISC-Law-SFT-Pair.jsonl", "问答"),
    "DISC-Law-Triplet": ("disc-law/DISC-Law-SFT-Triplet-released.jsonl", "问答"),
    "FinEval-MCQ": ("fineval/data-v2/FinEval_V2_no_test_ans/FinEval_V2_no_test_ans/dev/finance_dev.csv", "选择题"),
    "FinGPT": ("fingpt/data/train-00000-of-00001-dabab110260ac909.parquet", "问答"),
    "LawBench": ("lawbench/data/zero_shot/3-8.json", "问答"),
    "Huatuo": ("huatuo/huatuo.parquet", "问答"),
    "Toyhom": ("toyhom/样例_内科5000-6000.csv", "问答"),
}


@pytest.mark.parametrize("name", sorted(REAL_FILES))
def test_real_data_inspect(name):
    """每个真实数据集都能被 inspect 正确识别。"""
    rel, expected_type = REAL_FILES[name]
    path = DL / rel
    if not path.exists():
        pytest.skip(f"真实数据未下载：{rel}")
    s, err = inspect("医疗", [str(path)], limit=50)
    assert s is not None, f"{name} 识别失败：{err}"
    assert err == "", f"{name} 错误：{err}"
    assert s.type_counts.get(expected_type, 0) > 0, f"{name} 期望 {expected_type}>0，实际 {s.type_counts}"


@pytest.mark.parametrize("name", sorted(REAL_FILES))
def test_real_data_run_pipeline(name, tmp_path):
    """每个真实数据集都能被 run_pipeline 全量落盘。"""
    rel, _ = REAL_FILES[name]
    path = DL / rel
    if not path.exists():
        pytest.skip(f"真实数据未下载：{rel}")
    import llm_platform.data_pipeline.io as io_mod
    io_mod.DATA_DIR = tmp_path
    res = run_pipeline("医疗", [str(path)])
    assert res.kept > 0, f"{name} kept=0"
    out = tmp_path / "medical_alpaca.jsonl"
    assert out.exists(), f"{name} 输出文件不存在"
    first = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert set(first) == {"instruction", "input", "output"}, f"{name} Alpaca 格式错误"


# ========== 门面测试 ==========

class TestFacade:
    """inspect/run_pipeline 门面行为。"""

    def test_unsupported_domain_inspect(self):
        s, err = inspect("农业", ["fake.json"])
        assert s is None and "不支持" in err

    def test_unsupported_domain_run_pipeline(self):
        with pytest.raises(ValueError, match="不支持"):
            run_pipeline("农业", ["fake.json"])

    def test_empty_files_inspect(self):
        s, err = inspect("医疗", [])
        assert s is None and err == ""

    def test_empty_files_run_pipeline(self):
        with pytest.raises(ValueError, match="请先上传"):
            run_pipeline("医疗", [])

    def test_unrecognizable_data(self, tmp_path):
        f = tmp_path / "bad.jsonl"
        f.write_text('{"foo": "bar"}\n', encoding="utf-8")
        s, err = inspect("医疗", [str(f)])
        assert s is None and "未能识别" in err

    def test_mixed_upload(self):
        s, err = inspect("医疗", [str(SYNTH / "cmmlu.csv"), str(SYNTH / "medqa.jsonl")], limit=50)
        assert s is not None and err == "", err
        assert s.type_counts.get("选择题", 0) > 0


# ========== SCHEMAS 完整性测试 ==========

class TestSchemas:
    """SCHEMAS 注册完整性。"""

    def test_mcq_schemas(self):
        assert set(SCHEMAS["mcq"]) == {"CMB-Exam", "MedQA", "CMMLU/MMLU", "FinEval-MCQ"}

    def test_clin_schemas(self):
        assert set(SCHEMAS["clin"]) == {"CMB-Clin"}

    def test_qa_schemas(self):
        assert set(SCHEMAS["qa"]) == {
            "CrimeKG-QA", "DISC-Law-Pair", "DISC-Law-Triplet",
            "FinGPT-sentiment", "LawBench", "Huatuo-26M", "Toyhom",
        }

    def test_supported_domains(self):
        assert SUPPORTED == ["医疗", "法律", "金融", "教育"]

    def test_all_schemas_have_keys_and_fmt(self):
        for slug, datasets in SCHEMAS.items():
            for name, spec in datasets.items():
                assert "keys" in spec, f"{slug}/{name} 缺 keys"
                assert "fmt" in spec, f"{slug}/{name} 缺 fmt"