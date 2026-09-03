#!/usr/bin/env bash
# 一键操作本地 ⇄ AutoDL 云端（代码经 GitHub 远程仓库同步，不本地直传）
#   ./deploy.sh           云端 git clone/pull 同步代码 + 装依赖（不重装 torch）
#   ./deploy.sh logs      看云端日志
#   ./deploy.sh start     云端后台启动 app（需要已挂 GPU 卡）
# 用法：先 git push origin main，再 ./deploy.sh 让云端拉取最新代码
set -euo pipefail

SSH_ALIAS="${SSH_ALIAS:-autodl}"            # 对应 ~/.ssh/config 里的 Host（含 host/port/key）
REMOTE_DIR="/root/autodl-tmp/llm-platform"  # 放数据盘（持久、大、换镜像不丢）
GIT_REPO="${GIT_REPO:-https://github.com/g513yb/llm-platform}"  # 云端克隆的远程仓库
GIT_BRANCH="${GIT_BRANCH:-main}"           # 同步分支（先 push 到该分支，再 deploy）
SPARSE_PATHS="${SPARSE_PATHS:-app.py config.py requirements.txt run.sh start_app.sh llm_platform resources}"  # 云端运行所需顶层路径白名单（稀疏检出）；docs/README/CLAUDE/LICENSE/tests/samples/*.bat 等不检出
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

echo "[deploy] 云端通过 git 同步代码（浅克隆 + 稀疏检出，仅拉运行所需）..."
ssh "$SSH_ALIAS" "bash -s" <<EOF
set -euo pipefail
if [[ -d "$REMOTE_DIR/.git" ]]; then
  echo "[deploy] 远端已有仓库，fetch + reset --hard origin/$GIT_BRANCH ..."
  cd "$REMOTE_DIR"
  git fetch --depth=1 origin "$GIT_BRANCH"
  git reset --hard "origin/$GIT_BRANCH"
else
  echo "[deploy] 远端无仓库，clone $GIT_REPO ..."
  rm -rf "$REMOTE_DIR"
  git clone --depth=1 --sparse --branch "$GIT_BRANCH" "$GIT_REPO" "$REMOTE_DIR"
  cd "$REMOTE_DIR"
fi
git sparse-checkout init --cone 2>/dev/null || true
git sparse-checkout set $SPARSE_PATHS
echo "[deploy] 稀疏检出保留: $SPARSE_PATHS"
EOF

echo "[deploy] 装依赖（镜像已带 CUDA torch，跳过重装）..."
ssh "$SSH_ALIAS" "$REMOTE_INIT; cd $REMOTE_DIR && python -m pip install --upgrade pip -q && pip install -r requirements.txt -q"

echo "[deploy] 完成。挂卡后启动: ./deploy.sh start ；看日志: ./deploy.sh logs"
