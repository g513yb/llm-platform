"""对话管线：按 Qwen2.5 chat 模板编码 + model.generate + 流式输出。"""
import threading
from typing import Dict, List

import torch
from transformers import TextIteratorStreamer

from config import GENERATION
from llm_platform.model_manager import load_model, model_device


def stream_chat(messages: List[Dict[str, str]]):
    """逐 token 产出助手回复（同步生成器，适配 Gradio 流式 Chatbot）。

    messages: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
    """
    model, tokenizer = load_model()
    result = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,   # 拼接 <|im_start|>assistant
        return_tensors="pt",
    )
    # 兼容两种返回：apply_chat_template 可能返回 BatchEncoding(dict) 或纯 input_ids tensor
    if isinstance(result, dict):
        kwargs = {
            "input_ids": result["input_ids"].to(model_device()),
            "attention_mask": result["attention_mask"].to(model_device()),
        }
    else:
        # 纯 input_ids tensor（单条无 padding），attention_mask 全 1 即正确
        ids = result.to(model_device())
        kwargs = {
            "input_ids": ids,
            "attention_mask": torch.ones_like(ids),
        }

    streamer = TextIteratorStreamer(
        tokenizer,
        skip_prompt=True,             # 流里不含回显的 prompt
        skip_special_tokens=True,     # 去掉 <|im_end|> 等
        timeout=30.0,
    )
    gen_kwargs = dict(
        kwargs,
        streamer=streamer,
        pad_token_id=tokenizer.eos_token_id,
        **GENERATION,
    )
    thread = threading.Thread(target=model.generate, kwargs=gen_kwargs)
    thread.start()
    try:
        for chunk in streamer:
            yield chunk
    finally:
        thread.join()
