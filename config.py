"""全平台唯一配置源：模型、精度、生成参数、领域列表、数据/资源目录。
后续 Sprint 的数据/训练/评测配置也集中在此，便于一处管理。
"""
import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"          # 数据治理产物：sharegpt.jsonl/.json + config.json
RESOURCE_DIR = PROJECT_ROOT / "resources" # 领域预设资源（知识即数据）

# —— 基座模型 ——
# 可用环境变量 MODEL_NAME 覆盖，默认用 HuggingFace repo id（任意机器可下载）。
# AutoDL 上连不上 huggingface.co，部署脚本（run.sh / start_app.sh）会把它设为本地 ModelScope 路径。
MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
MODEL_SHORT_NAME = MODEL_NAME.split("/")[-1]

# —— 设备 / 精度 ——
# FORCE_DEVICE：None=自动探测（优先认 FORCE_DEVICE）；"cuda" 强制；"cpu" 仅本地调试（7B 会极慢/报错）。
# 可用环境变量覆盖，便于本机调试不污染云端默认。
FORCE_DEVICE = os.environ.get("FORCE_DEVICE")   # None 或 "cuda"/"cpu"
# QUANTIZATION：可被环境变量覆盖；云端默认 "none"；本地 12GB 显存跑 7B 用 "4bit"。
QUANTIZATION = os.environ.get("QUANTIZATION", "none")   # "none" | "8bit" | "4bit"（8bit/4bit 需 bitsandbytes + GPU）

# —— 生成默认参数（对话 Tab 使用）——
GENERATION = dict(
    max_new_tokens=1024,
    do_sample=True,
    temperature=0.7,
    top_p=0.9,
)

# —— 应用 ——
APP_TITLE = "多域 LLM 微调与评测平台"
DEFAULT_DEVICE_MAP = "auto"
OUTPUT_FORMAT = "alpaca"   # 训练数据输出格式："alpaca"(instruction/input/output, 默认) | "sharegpt"(messages)

# —— 领域注册表：(标签, 描述) ——
DOMAINS = [
    ("医疗", "医疗领域：病历、文献、诊断建议"),
    ("法律", "法律领域：法规、案例、合同审查"),
    ("金融", "金融领域：研报、财报、风控"),
    ("教育", "教育领域：课程、试题、答疑"),
]

# 领域中文标签 -> 资源目录 slug（ASCII，便于文件/目录路径）
DOMAIN_SLUGS = {"医疗": "medical", "法律": "legal", "金融": "finance", "教育": "education"}
