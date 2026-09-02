"""懒加载单例：按需加载基座模型与 tokenizer，全进程只加载一次。

Sprint 0 仅用于 GPU 推理；后续 Sprint 的 LoRA 会基于这里加载的基座继续挂 adapter。
"""
from typing import Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from config import MODEL_NAME, QUANTIZATION, DEFAULT_DEVICE_MAP

_model = None
_tokenizer = None
_device = None


def _pick_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    raise RuntimeError(
        "CUDA 不可用：运行本应用需要 GPU 才能加载基座模型。\n"
        "请在 AutoDL 等 GPU 实例上运行，或把 config.MODEL_NAME 换成可 CPU 推理的小模型。"
    )


def _pick_dtype() -> torch.dtype:
    # A100/4090/Ada (cap[0]>=8) 用 bf16；更老卡用 fp16；CPU 兜底 float32。
    if not torch.cuda.is_available():
        return torch.float32
    major, _ = torch.cuda.get_device_capability()
    return torch.bfloat16 if major >= 8 else torch.float16


def load_model(device_map: Optional[str] = None):
    """返回 (model, tokenizer)。首次调用才真正加载，之后直接给缓存。"""
    global _model, _tokenizer, _device
    if _model is not None:
        return _model, _tokenizer

    _device = _pick_device()
    dtype = _pick_dtype()
    print(f"[model] 正在加载 {MODEL_NAME} 到 {_device}（dtype={dtype}）...", flush=True)

    # Qwen2.5 无 pad token，复用 eos 避免 padding/batch 报错
    _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    if _tokenizer.pad_token is None:
        _tokenizer.pad_token = _tokenizer.eos_token

    kwargs = {"torch_dtype": dtype, "device_map": device_map or DEFAULT_DEVICE_MAP}
    if QUANTIZATION == "8bit":
        from transformers import BitsAndBytesConfig
        kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)

    # transforms>=4.37 原生识别 Qwen2/Qwen2.5，无需 trust_remote_code
    _model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, **kwargs)
    _model.eval()
    print(f"[model] {MODEL_NAME} 已就绪（device={_device}）", flush=True)
    return _model, _tokenizer


def warm_up():
    """应用启动时预热：先下载/加载权重，避免用户首条消息等待过久。"""
    return load_model()


def model_device() -> str:
    return _device
