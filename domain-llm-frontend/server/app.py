import gc
import json
import os
import shutil
import uuid
from threading import Lock, Thread

import torch
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from peft import PeftModel
from pydantic import BaseModel
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TextIteratorStreamer,
)
import uvicorn

import training
from dataset_utils import parse_dataset

MODEL_PATH = r"C:\Qwen2.5-3B-Instruct"
PORT = 8000

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
)

base_model = None
infer_model = None
tokenizer = None
adapter_lock = Lock()
model_lock = Lock()
active_adapter = {"id": None, "name": "基座模型"}
current_model_path = MODEL_PATH


def ensure_model_loaded():
    global base_model, infer_model, tokenizer
    with model_lock:
        if base_model is not None:
            return True, ""
        try:
            print(f"首次加载模型（4bit 量化）：{current_model_path}", flush=True)
            tok = AutoTokenizer.from_pretrained(current_model_path)
            if tok.pad_token is None:
                tok.pad_token = tok.eos_token
            m = AutoModelForCausalLM.from_pretrained(
                current_model_path,
                quantization_config=bnb_config,
                device_map={"": 0},
            )
            m.eval()
            tokenizer = tok
            base_model = m
            infer_model = m
            print("模型加载完成。", flush=True)
            return True, ""
        except Exception as e:
            return False, str(e)


def release_infer_model():
    global base_model, infer_model
    try:
        if infer_model is not None and infer_model is not base_model:
            del infer_model
        if base_model is not None:
            del base_model
    except Exception:
        pass
    base_model = None
    infer_model = None
    gc.collect()
    torch.cuda.empty_cache()


def reload_infer_model():
    global base_model, infer_model, active_adapter, tokenizer
    gc.collect()
    torch.cuda.empty_cache()
    try:
        base_model = AutoModelForCausalLM.from_pretrained(
            current_model_path, quantization_config=bnb_config, device_map={"": 0}
        )
        base_model.eval()
        if tokenizer is None:
            tokenizer = AutoTokenizer.from_pretrained(current_model_path)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
        infer_model = base_model
        active_adapter = {"id": None, "name": "基座模型"}
    except Exception as e:
        print(f"重载推理模型失败: {e}", flush=True)
        base_model = None
        infer_model = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    max_new_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9


app = FastAPI(title="Domain-LLM Local Inference")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "model": "Qwen2.5-3B-Instruct", "quant": "4bit", "ready": infer_model is not None}


class TrainRequest(BaseModel):
    name: str
    datasetId: str
    datasetLabel: str = ""
    modelPath: str = ""
    domain: str = ""
    rank: int = 16
    lr: str = "2e-4"
    epochs: int = 3
    batch: int = 8


@app.post("/api/datasets/upload")
async def upload_dataset(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".csv", ".txt", ".json", ".jsonl"):
        return {"error": "仅支持 csv/txt/json/jsonl 格式"}
    dataset_id = f"ds-{uuid.uuid4().hex[:8]}"
    save_path = os.path.join(training.DATASET_DIR, f"{dataset_id}_{file.filename}")
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        samples = parse_dataset(save_path)
        return {
            "datasetId": dataset_id,
            "filename": file.filename,
            "size": os.path.getsize(save_path),
            "samples": len(samples),
        }
    except Exception as e:
        return {"datasetId": dataset_id, "filename": file.filename, "error": str(e)}


@app.post("/api/train")
async def start_training(req: TrainRequest):
    global current_model_path
    files = [f for f in os.listdir(training.DATASET_DIR) if f.startswith(req.datasetId + "_")]
    if not files:
        return {"error": "数据集不存在，请先上传"}
    dataset_path = os.path.join(training.DATASET_DIR, files[0])
    model_path = req.modelPath.strip() or MODEL_PATH
    current_model_path = model_path
    task_id = f"tk-{uuid.uuid4().hex[:8]}"
    training.start_job(task_id, dataset_path, req.rank, req.lr, req.epochs, req.batch, req.name, req.domain, req.datasetLabel, model_path, release_infer_model, reload_infer_model)
    return {"taskId": task_id, "name": req.name}


@app.get("/api/train/jobs")
def list_jobs_api():
    return training.list_jobs()


@app.get("/api/train/{task_id}/status")
async def train_status(task_id: str):
    return training.get_status(task_id)


@app.post("/api/train/{task_id}/stop")
def stop_job_api(task_id: str):
    ok = training.stop_job(task_id)
    return {"ok": ok} if ok else {"error": "任务不存在"}


@app.delete("/api/train/{task_id}")
def delete_job_api(task_id: str):
    training.delete_job(task_id)
    return {"ok": True}


class LoadAdapterRequest(BaseModel):
    adapterId: str | None = None


@app.get("/api/adapters")
def list_adapters_api():
    return training.list_adapters()


@app.get("/api/adapters/active")
def active_adapter_api():
    return active_adapter


@app.post("/api/adapters/load")
def load_adapter(req: LoadAdapterRequest):
    global infer_model, active_adapter
    ok, err = ensure_model_loaded()
    if not ok:
        return {"error": f"模型加载失败：{err}"}
    with adapter_lock:
        aid = req.adapterId
        if not aid:
            infer_model = base_model
            active_adapter = {"id": None, "name": "基座模型"}
            return active_adapter
        info = next((a for a in training.list_adapters() if a["id"] == aid), None)
        if not info:
            return {"error": "权重不存在"}
        if infer_model is not base_model:
            try:
                infer_model.unload()
            except Exception:
                pass
            infer_model = base_model
            gc.collect()
            torch.cuda.empty_cache()
        infer_model = PeftModel.from_pretrained(base_model, info["adapter_path"])
        infer_model.eval()
        active_adapter = {"id": aid, "name": info["name"]}
        return active_adapter


@app.post("/api/chat")
async def chat(req: ChatRequest):
    msgs = [{"role": m.role, "content": m.content} for m in req.messages]
    ok, err = ensure_model_loaded()
    if not ok:
        async def err_stream():
            yield f"data: {json.dumps({'token': f'⚠️ 模型加载失败：{err}'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(err_stream(), media_type="text/event-stream")
    if infer_model is None:
        async def err_stream():
            yield f"data: {json.dumps({'token': '⚠️ 模型尚未就绪（可能正在训练或加载中），请稍后重试。'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(err_stream(), media_type="text/event-stream")
    prompt = tokenizer.apply_chat_template(
        msgs, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(prompt, return_tensors="pt").to(infer_model.device)
    streamer = TextIteratorStreamer(
        tokenizer, skip_prompt=True, skip_special_tokens=True
    )
    gen_kwargs = dict(
        input_ids=inputs["input_ids"],
        attention_mask=inputs.get("attention_mask"),
        streamer=streamer,
        max_new_tokens=req.max_new_tokens,
        temperature=req.temperature,
        top_p=req.top_p,
        do_sample=True,
        pad_token_id=tokenizer.pad_token_id,
    )

    m = infer_model

    def event_stream():
        thread = Thread(target=m.generate, kwargs=gen_kwargs)
        thread.start()
        for text in streamer:
            if text:
                yield f"data: {json.dumps({'token': text}, ensure_ascii=False)}\n\n"
        thread.join()
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT)