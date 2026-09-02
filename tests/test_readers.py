"""reader 级测试：对每个真实/重排数据源 fixture 跑 read_inputs，断言归一化结构。

只做结构化断言（不写盘、不涉及 keep/drop）；断言按冻结后的真实 fixture 内容校写。
"""
from __future__ import annotations

import unittest

from tests._helpers import reader


class TestReaders(unittest.TestCase):
    """归一化不变量：至少一条、首 user 尾 assistant、内容非空；再按各源特征标记断言。"""

    def _assert_pair(self, items, user_marker=None, asst_marker=None, asst_start=None, asst_end=None):
        self.assertGreater(len(items), 0, "rows_loaded 应为 0")
        for it in items:
            msgs = it.messages
            self.assertGreaterEqual(len(msgs), 2, "至少应有 user+assistant")
            self.assertEqual(msgs[0]["role"], "user")
            self.assertEqual(msgs[-1]["role"], "assistant")
            for m in msgs:
                self.assertTrue(m["content"].strip(), "content 不应为空")
            user = msgs[0]["content"]
            asst = msgs[-1]["content"]
            if user_marker:
                self.assertIn(user_marker, user)
            if asst_marker:
                self.assertIn(asst_marker, asst)
            if asst_start:
                self.assertTrue(asst.startswith(asst_start), f"{asst[:40]!r} 应以 {asst_start!r} 开头")
            if asst_end:
                self.assertTrue(asst.endswith(asst_end), f"{asst[:40]!r} 应以 {asst_end!r} 结尾")

    # ---- 医疗 ----
    def test_cmb_exam(self):
        self._assert_pair(reader("cmb_exam_medical.jsonl"),
                          user_marker="单选题：", asst_start="答案")

    def test_cmb_clin(self):
        # 真实 CMB-Clin：QA_pairs 用 answer 键（reader 已做 solution/answer 兼容）
        self._assert_pair(reader("cmb_clin_medical.jsonl"), asst_marker="诊断")

    def test_cmb_clin_bad_normalizes(self):
        # 构造坏样本也能被正常归一化（丢弃发生在预设级，而非 reader）
        self._assert_pair(reader("cmb_clin_medical_cn_bad.jsonl"))

    def test_toyhom_gbk(self):
        self._assert_pair(reader("toyhom_medical.csv"), user_marker="科室：", asst_marker="党参")

    def test_medqa(self):
        self._assert_pair(reader("medqa_medical.jsonl"),
                          user_marker="题：", asst_start="答案", asst_marker="解析")

    def test_huatuo(self):
        self._assert_pair(reader("huatuo_medical.jsonl"), user_marker="高血压")

    def test_raw_medical_txt(self):
        # 纯文本必须走 read_txt_raw（.txt → medical 生成器）；NFKC 会把全角冒号转半角
        self._assert_pair(reader("raw_medical.txt", "medical"), asst_start="主诉", asst_marker="诊断")

    # ---- 法律 ----
    def test_disc_law_alpaca(self):
        self._assert_pair(reader("disc_law_legal.jsonl"), user_marker="纠正下面法律文书")

    def test_lawbench_qa(self):
        self._assert_pair(reader("lawbench_qa_legal.jsonl"),
                          user_marker="上诉证据收集程序合法", asst_start="上述证据")

    def test_lawbench_summary(self):
        # 必须命中 article+summary 分支（用 output 会被 Alpaca 分支吞掉）
        self._assert_pair(reader("lawbench_summary_legal.jsonl"),
                          user_marker="第二百六十四条", asst_marker="盗窃罪")

    def test_raw_legal_judgment_txt(self):
        self._assert_pair(reader("raw_legal_judgment.txt", "legal"), asst_marker="判决书")

    def test_raw_legal_judgment_bad_txt(self):
        self._assert_pair(reader("raw_legal_judgment_cn_bad.txt", "legal"), asst_marker="判决书")

    def test_raw_legal_contract_txt(self):
        self._assert_pair(reader("raw_legal_contract.txt", "legal"), user_marker="甲方", asst_marker="甲方")

    # ---- 金融 ----
    def test_fineval_mcq(self):
        self._assert_pair(reader("fineval_mcq_finance.jsonl"), user_marker="题：", asst_start="答案")

    def test_fineval_qa(self):
        self._assert_pair(reader("fineval_qa_finance.jsonl"), asst_marker="党参")

    def test_fingpt_input_output(self):
        # branch ⑧：只有 input+output（无 instruction/question/answer）
        self._assert_pair(reader("fingpt_finance.jsonl"),
                          user_marker="公司发布业绩预告", asst_start="positive")

    def test_finance_report(self):
        self._assert_pair(reader("finance_report_cn.jsonl"), user_marker="亿元", asst_marker="亿元")

    # ---- 教育 ----
    def test_mmlu_csv(self):
        self._assert_pair(reader("mmlu_education.csv"),
                          user_marker="下列鸭品种", asst_start="答案", asst_end="D")

    def test_cmmlu_csv(self):
        # 大写列头 + 前导序号列，reader 应正确识别 MCQ 分支
        self._assert_pair(reader("cmmlu_education.csv"),
                          user_marker="下列鸭品种", asst_start="答案", asst_end="D")

    def test_educhat_alpaca(self):
        self._assert_pair(reader("educhat_education.jsonl"),
                          user_marker="解释光合作用", asst_marker="光合作用")

    def test_educhat_cn_bad_alpaca(self):
        self._assert_pair(reader("educhat_education_cn_bad.jsonl"), user_marker="学习的看法")

    def test_fingpt_cn_bad_normalizes(self):
        self._assert_pair(reader("fingpt_finance_cn_bad.jsonl"), asst_start="positive")


if __name__ == "__main__":
    unittest.main()
