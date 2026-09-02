#!/usr/bin/env bash
# 一键操作本地代码 <-> AutoDL 云端
#   ./deploy.sh           推代码 + 装依赖（不重装 torch）
#   ./deploy.sh logs      看云端日志
#   ./deploy.sh start     云端后台启动 app（需要已挂 GPU 卡）
set -euo pipefail

SSH_ALIAS="${SSH_ALIAS:-autodl}"            # 对应 ~/.ssh/config 里的 Host（含 host/port/key）
REMOTE_DIR="/root/autodl-tmp/llm-platform"  # 放数据盘（持久、大、换镜像不丢）
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"
REMOTE_INIT="source /root/miniconda3/etc/profile.d/conda.sh 2>/dev/null && conda activate base 2>/dev/null"

if [[ "${1:-}" == "logs" ]]; then
  exec ssh "$SSH_ALIAS" "$REMOTE_INIT; tail -n 100 $REMOTE_DIR/app.log"
fi

if [[ "${1:-}" == "start" ]]; then
  echo "[deploy] 云端后台启动 app（需 GPU 卡）..."
  # 用 start_app.sh + setsid 真正脱离 ssh 会话，避免断开后被 SIGHUP 杀掉
  ssh "$SSH_ALIAS" "cd $REMOTE_DIR && setsid nohup bash $REMOTE_DIR/start_app.sh > $REMOTE_DIR/app.log 2>&1 < /dev/null & echo started"
  echo "已在云端后台启动。日志: ./deploy.sh logs ；实时: ssh $SSH_ALIAS 'tail -f $REMOTE_DIR/app.log'"
  exit 0
fi

echo "[deploy] 创建云端目录: $REMOTE_DIR ..."
ssh "$SSH_ALIAS" "mkdir -p $REMOTE_DIR"

echo "[deploy] 同步本地代码到云端 ..."
scp -rq "$LOCAL_DIR/." "$SSH_ALIAS:$REMOTE_DIR/"

echo "[deploy] 装依赖（镜像已带 CUDA torch，跳过重装）..."
ssh "$SSH_ALIAS" "$REMOTE_INIT; cd $REMOTE_DIR && python -m pip install --upgrade pip -q && pip install -r requirements.txt -q"

echo "[deploy] 完成。挂卡后启动: ./deploy.sh start ；看日志: ./deploy.sh logs"
