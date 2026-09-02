"""测试公共装具：仓库根路径置顶、fixture 目录、Hermetic PipelineTestCase。

不直接作为测试被发现（文件名不以 test 开头）。供 test_readers.py / test_pipeline.py 复用。
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from llm_platform.data_pipeline.readers import read_inputs
from llm_platform.data_pipeline.txt_generator import make_txt_reader

# 仓库根（tests/ 的上一级），保证任意运行方式都能 import config / llm_platform
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def reader(path: str, slug: str | None = None) -> list:
    """对单个 fixture 跑 read_inputs（返回 WorkItem 列表）；.txt 必须传 read_txt_raw。"""
    kw = {"read_txt_raw": make_txt_reader(slug)} if slug else {}
    items, _meta = read_inputs([str(FIXTURES / path)], **kw)
    return items


class PipelineTestCase(unittest.TestCase):
    """Hermetic：每个测试获得独立临时 DATA_DIR，输出互不干扰、不污染 data/。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = mock.patch(
            "llm_platform.data_pipeline.io.DATA_DIR", Path(self._tmp.name)
        )
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        self._tmp.cleanup()

    def read_output(self, summary):
        """read_output_files[0]（.jsonl）并解析为 [dict, ...]。"""
        self.assertEqual(len(summary.output_files), 3, summary.output_files)
        jsonl = summary.output_files[0]
        rows = [
            json.loads(line)
            for line in Path(jsonl).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return jsonl, rows
