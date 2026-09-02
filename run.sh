#!/usr/bin/env bash
# AutoDL 一键启动：仅补装缺失依赖 + 运行应用（镜像已带 CUDA torch，勿重装）
set -euo pipefail
cd "$(dirname "$0")"

# —— 激活 AutoDL 的 conda 基础环境（非交互 SSH 默认不激活）——
if [ -f /root/miniconda3/etc/profile.d/conda.sh ]; then
  source /root/miniconda3/etc/profile.d/conda.sh && conda activate base
elif [ -f /opt/conda/etc/profile.d/conda.sh ]; then
  source /opt/conda/etc/profile.d/conda.sh && conda activate base
fi

# —— 模型权重落数据盘（系统盘小且重启易丢失）；若没有数据盘则回退默认缓存 ——
HF_DIR="/root/autodl-tmp/llm-platform/hf"
if mkdir -p "$HF_DIR" 2>/dev/null; then
  export HF_HOME="$HF_DIR"
  echo "[run] 模型缓存将存放到数据盘：$HF_DIR"
fi

# —— 云端无 huggingface 访问，显式用本地 ModelScope 权重路径（可被环境变量覆盖）——
export MODEL_NAME="${MODEL_NAME:-/root/autodl-tmp/llm-platform/models/Qwen2.5-7B-Instruct}"

# —— 学术加速是 AutoDL 控制台的手动开关，脚本无法开启 ——
#   请在 AutoDL 实例页 ->「学术加速」自行打开，可显著加快首次模型下载。
#   或临时改用 HF 镜像端点加速下载，取消下面一行注释：
# export HF_ENDPOINT=https://hf-mirror.com

pip install --upgrade pip
pip install -r requirements.txt

python app.py
