"""pipeline 级测试：对每个数据源跑 run_pipeline(领域, file_paths, preset)。

Hermetic（临时 DATA_DIR，见 PipelineTestCase）。断言按真实运行结果锁定：
- 宽松 _qa / 严格 _cn good → kept>=1；
- 严格 _cn bad → dropped>=1 且 drop_reasons 键以特定前缀开头（用 startswith，因后缀随内容变化）。
输出行恒为 {instruction,input,output,source}；instruction/output 非空。
input 可空（纯问答/选择题）或非空（CMB-Clin/Alpaca/纯文本等有显式背景拆分）。
"""
from __future__ import annotations

import unittest

from llm_platform.data_pipeline import run_pipeline

from tests._helpers import PipelineTestCase, FIXTURES


class _Base(PipelineTestCase):
    domain = ""
    def _run(self, name, preset, **kw):
        return run_pipeline(self.domain, file_paths=[str(FIXTURES / name)], preset=preset, **kw)

    def _assert_rows(self, summary, output_start=None, output_end=None, output_in=None,
                     input_nonempty=None, input_in=None):
        """验证输出行结构 + 内容。

        input_nonempty=True  → 断言 input 非空（有显式背景拆分）；
        input_nonempty=False → 断言 input 为空（纯问答/选择题）；
        input_nonempty=None  → 不断言 input（向后兼容）。
        """
        self.assertGreater(summary.kept, 0)
        _, rows = self.read_output(summary)
        for r in rows:
            self.assertEqual(set(r), {"instruction", "input", "output", "source"}, r)
            self.assertTrue(r["instruction"].strip(), f"instruction 空：{r}")
            self.assertTrue(r["output"].strip(), f"output 空：{r}")
            if input_nonempty is True:
                self.assertTrue(r["input"].strip(), f"input 应非空但为空：{r}")
            elif input_nonempty is False:
                self.assertEqual(r["input"], "", f"input 应空但非空：{r}")
            if input_in:
                self.assertIn(input_in, r["input"], f"input 未含 {input_in!r}：{r}")
            if output_start:
                self.assertTrue(r["output"].startswith(output_start), r["output"])
            if output_end:
                self.assertTrue(r["output"].endswith(output_end), r["output"])
            if output_in:
                self.assertIn(output_in, r["output"])


class TestMedical(_Base):
    domain = "医疗"

    def test_cmb_exam_medical_qa_kept(self):
        self._assert_rows(self._run("cmb_exam_medical.jsonl", "medical_qa"), output_start="答案", input_nonempty=False)

    def test_cmb_clin_medical_qa_kept(self):
        # 真实 CMB-Clin（QA_pairs 用 answer 键）在宽松预设下保留；description 进 input
        self._assert_rows(self._run("cmb_clin_medical.jsonl", "medical_qa"), output_in="诊断", input_nonempty=True, input_in="现病史")

    def test_toyhom_medical_qa_kept(self):
        self._assert_rows(self._run("toyhom_medical.csv", "medical_qa"), output_in="党参", input_nonempty=False)

    def test_medqa_medical_qa_kept(self):
        self._assert_rows(self._run("medqa_medical.jsonl", "medical_qa"), output_start="答案", input_nonempty=False)

    def test_huatuo_medical_qa_kept(self):
        self._assert_rows(self._run("huatuo_medical.jsonl", "medical_qa"), output_in="党参", input_nonempty=False)

    def test_raw_medical_medical_cn_kept(self):
        # 纯文本生成：含主诉+诊断 → 医疗严格预设保留；病历原文进 input
        s = self._run("raw_medical.txt", "medical_cn")
        self.assertEqual(s.total, 1); self.assertEqual(s.dropped, 0)
        self._assert_rows(s, output_in="主诉", input_nonempty=True)

    def test_cmb_clin_medical_cn_dropped(self):
        # 真实 CMB-Clin 病历缺"诊断"小节 → 严格预设按文档规则丢弃
        s = self._run("cmb_clin_medical.jsonl", "medical_cn")
        self.assertEqual(s.total, 1); self.assertEqual(s.kept, 0); self.assertEqual(s.dropped, 1)
        self.assertTrue(any(k.startswith("临床信息不完整") for k in s.drop_reasons), s.drop_reasons)

    def test_cmb_clin_bad_medical_cn_dropped(self):
        s = self._run("cmb_clin_medical_cn_bad.jsonl", "medical_cn")
        self.assertEqual(s.dropped, 1); self.assertEqual(s.kept, 0)
        self.assertTrue(any(k.startswith("临床信息不完整") for k in s.drop_reasons), s.drop_reasons)


class TestLegal(_Base):
    domain = "法律"

    def test_lawbench_qa_legal_qa_kept(self):
        self._assert_rows(self._run("lawbench_qa_legal.jsonl", "legal_qa"), output_start="上述证据", input_nonempty=False)

    def test_lawbench_qa_legal_cn_dropped(self):
        # 纯问答无文书结构 → legal_cn 质量分过低丢弃
        s = self._run("lawbench_qa_legal.jsonl", "legal_cn")
        self.assertEqual(s.dropped, 1); self.assertEqual(s.kept, 0)
        self.assertTrue(any(k.startswith("结构/领域质量分过低") for k in s.drop_reasons), s.drop_reasons)

    def test_disc_law_legal_qa_kept(self):
        # 原始 Alpaca 有 instruction/input 拆分，input 应保留
        self._assert_rows(self._run("disc_law_legal.jsonl", "legal_qa"), input_nonempty=True)

    def test_lawbench_summary_legal_qa_kept(self):
        # article 进 input
        self._assert_rows(self._run("lawbench_summary_legal.jsonl", "legal_qa"), output_in="盗窃罪", input_nonempty=True)

    def test_raw_legal_judgment_legal_cn_kept(self):
        # 真实判决书较长（>默认 max_len），需放大 max_len 才能保留；判决书原文进 input
        s = self._run("raw_legal_judgment.txt", "legal_cn", max_len=30000)
        self.assertEqual(s.total, 1); self.assertEqual(s.dropped, 0); self.assertEqual(s.kept, 1)
        self._assert_rows(s, output_in="判决书", input_nonempty=True)

    def test_raw_legal_judgment_bad_cn_dropped(self):
        # 缺案号 → 判决书必备要素缺失（合同/法规 drop:false，故不可用作 bad）
        s = self._run("raw_legal_judgment_cn_bad.txt", "legal_cn")
        self.assertEqual(s.dropped, 1); self.assertEqual(s.kept, 0)
        self.assertTrue(any(k.startswith("判决书必备要素缺失") for k in s.drop_reasons), s.drop_reasons)

    def test_raw_legal_contract_legal_cn_kept(self):
        # 合同为 drop:false：缺要素仅警告，仍保留；合同原文进 input
        s = self._run("raw_legal_contract.txt", "legal_cn")
        self.assertEqual(s.total, 1); self.assertEqual(s.dropped, 0); self.assertEqual(s.kept, 1)
        self._assert_rows(s, input_nonempty=True)


class TestFinance(_Base):
    domain = "金融"

    def test_fineval_mcq_finance_qa_kept(self):
        self._assert_rows(self._run("fineval_mcq_finance.jsonl", "finance_qa"), output_start="答案", input_nonempty=False)

    def test_fineval_qa_finance_qa_kept(self):
        self._assert_rows(self._run("fineval_qa_finance.jsonl", "finance_qa"), input_nonempty=False)

    def test_fingpt_finance_qa_kept(self):
        self._assert_rows(self._run("fingpt_finance.jsonl", "finance_qa"), output_start="positive", input_nonempty=False)

    def test_fingpt_finance_cn_dropped(self):
        # 无"数值+单位"指标 → finance_cn 丢弃
        s = self._run("fingpt_finance.jsonl", "finance_cn")
        self.assertEqual(s.dropped, 1); self.assertEqual(s.kept, 0)
        self.assertTrue(any(k.startswith("缺少带单位的数值指标") for k in s.drop_reasons), s.drop_reasons)

    def test_fingpt_cn_bad_dropped(self):
        s = self._run("fingpt_finance_cn_bad.jsonl", "finance_cn")
        self.assertEqual(s.dropped, 1)
        self.assertTrue(any(k.startswith("缺少带单位的数值指标") for k in s.drop_reasons), s.drop_reasons)

    def test_finance_report_cn_kept(self):
        s = self._run("finance_report_cn.jsonl", "finance_cn")
        self.assertEqual(s.total, 1); self.assertEqual(s.dropped, 0); self.assertEqual(s.kept, 1)
        self._assert_rows(s, output_in="亿元", input_nonempty=True)


class TestEducation(_Base):
    domain = "教育"

    def test_mmlu_cn_kept(self):
        s = self._run("mmlu_education.csv", "education_cn")
        self.assertEqual(s.total, 1); self.assertEqual(s.dropped, 0); self.assertEqual(s.kept, 1)
        self._assert_rows(s, output_start="答案", output_end="D", input_nonempty=False)

    def test_cmmlu_cn_kept(self):
        # 大写列头+前导序号列（与真实 CMMLU 一致）
        s = self._run("cmmlu_education.csv", "education_cn")
        self.assertEqual(s.total, 1); self.assertEqual(s.dropped, 0); self.assertEqual(s.kept, 1)
        self._assert_rows(s, output_start="答案", output_end="D", input_nonempty=False)

    def test_educhat_education_qa_kept(self):
        self._assert_rows(self._run("educhat_education.jsonl", "education_qa"), output_in="光合作用", input_nonempty=False)

    def test_educhat_education_cn_dropped(self):
        # 开放问答无选项/答案 → education_cn 丢弃
        s = self._run("educhat_education.jsonl", "education_cn")
        self.assertEqual(s.dropped, 1); self.assertEqual(s.kept, 0)
        self.assertTrue(any(k.startswith("缺少选项或答案") for k in s.drop_reasons), s.drop_reasons)

    def test_educhat_cn_bad_dropped(self):
        s = self._run("educhat_education_cn_bad.jsonl", "education_cn")
        self.assertEqual(s.dropped, 1)
        self.assertTrue(any(k.startswith("缺少选项或答案") for k in s.drop_reasons), s.drop_reasons)


if __name__ == "__main__":
    unittest.main()
