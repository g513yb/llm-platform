#!/usr/bin/env bash
# 云端后台启动脚本：由 deploy.sh start 通过 setsid 调用，真正后台运行（不受 ssh 断开影响）
set -euo pipefail
cd "$(dirname "$0")"                       # 项目根 = /root/autodl-tmp/llm-platform

export HF_HOME="$PWD/hf"                   # 权重落数据盘
mkdir -p "$HF_HOME"

# 云端无 huggingface 访问，显式用本地 ModelScope 权重路径（可被环境变量覆盖）
export MODEL_NAME="${MODEL_NAME:-/root/autodl-tmp/llm-platform/models/Qwen2.5-7B-Instruct}"

source /root/miniconda3/etc/profile.d/conda.sh 2>/dev/null && conda activate base

pkill -f "python app.py" 2>/dev/null || true   # 干掉旧实例（若有）

cd server && exec python app.py                # exec 替换为 python 进程（在 server/ 内运行，同目录导入 training/dataset_utils）
