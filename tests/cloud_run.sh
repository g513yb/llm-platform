#!/usr/bin/env bash
# 云端一键测试流水线：下载数据 → 跑测试 → 生成可视化报告（由 ./deploy.sh datatest 调用）
# 注：build_fixtures.py 已随数据处理模块重做删除；fixtures 由新测试按需自带。
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== [1/3] 下载数据集（幂等：已下载跳过；HF_ENDPOINT 可指镜像）=="
python tests/download_datasets.py --all ${DOWNLOAD_FLAGS:-}

echo "== [2/3] 运行测试并生成可视化报告（自包含 HTML + JSON）=="
python tests/run_and_report.py --html tests/report.html --json tests/report.json

echo "== [3/3] 完成 =="
echo "报告:  $PWD/tests/report.html"
echo "数据:  $PWD/tests/report.json"
echo "本地查看: 在仓库根执行 ./deploy.sh report（端口转发）"
