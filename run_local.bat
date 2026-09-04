@echo off
rem 本机（有 NVIDIA GPU + 已下模型）启动器：加载 Qwen2.5 + 4bit 量化 + 流式对话。
rem 仅在带 GPU 的机器上运行；本机（无卡）仍用 .venv-verify 跑数据处理。
setlocal
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set QUANTIZATION=4bit

rem 本地模型目录（改这里，或启动前  set MODEL_NAME=你的路径  覆盖它）
if "%MODEL_NAME%"=="" set MODEL_NAME=D:\models\Qwen2.5-7B-Instruct

if not exist "%MODEL_NAME%" (
  echo [run_local] 找不到模型目录：%MODEL_NAME%
  echo 修改本文件 MODEL_NAME，或先  set MODEL_NAME=你的路径  再运行
  exit /b 1
)
if not exist ".venv-local\Scripts\python.exe" (
  echo [run_local] 未找到 .venv-local，请先运行 setup_local.bat 建本地 GPU 环境
  exit /b 1
)

pushd server
"%~dp0.venv-local\Scripts\python.exe" app.py
popd
