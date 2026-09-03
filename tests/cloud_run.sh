#!/usr/bin/env bash
# 云端一键测试流水线：下载数据 → 重建 fixtures → 跑测试 → 生成可视化报告（由 ./deploy.sh datatest 调用）
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== [1/4] 下载数据集（幂等：已下载跳过；HF_ENDPOINT 可指镜像）=="
python tests/download_datasets.py --all ${DOWNLOAD_FLAGS:-}

echo "== [2/4] 重建 test fixtures（从下载的真实源截取小样本）=="
python tests/build_fixtures.py

echo "== [2b/4] 校验关键 fixture 齐全 =="
python tests/build_fixtures.py --check

echo "== [3/4] 运行测试并生成可视化报告（自包含 HTML + JSON）=="
python tests/run_and_report.py --html tests/report.html --json tests/report.json

echo "== [4/4] 完成 =="
echo "报告:  $PWD/tests/report.html"
echo "数据:  $PWD/tests/report.json"
echo "本地查看: 在仓库根执行 ./deploy.sh report（端口转发）"