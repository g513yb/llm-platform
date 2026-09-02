@echo off
rem 本机（有 NVIDIA GPU）一次性环境：新建 .venv-local 并安装 torch(CUDA)+依赖+bitsandbytes。
rem 仅在带 GPU 的机器上运行；本机（无卡）请跳过，继续用 .venv-verify。
setlocal

echo [setup_local] 创建 .venv-local ...
python -m venv .venv-local
.venv-local\Scripts\pip install --upgrade pip

echo [setup_local] 安装 CUDA 版 torch（本机 driver 匹配 cu121/cu124/cu128，见下方注释）...
rem 4070=Ada(compute 8.9)；按本机 NVIDIA driver 调整：cu121 / cu124 / cu128
.venv-local\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cu124

echo [setup_local] 安装项目依赖 ...
.venv-local\Scripts\pip install -r requirements.txt

echo [setup_local] 安装 bitsandbytes（Windows 需 >=0.43）...
.venv-local\Scripts\pip install bitsandbytes --upgrade

echo [setup_local] 完成。把模型路径用环境变量/run_local.bat 指定后运行 run_local.bat。
