import gc
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from threading import Lock, Thread

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn

import training
import evaluation
from eval_runner import DEFAULT_TEST_PATH, DEFAULT_ANSWER_PATH, DEFAULT_GEN_CONFIG

from config import MODEL_NAME, QUANTIZATION, DEFAULT_DEVICE_MAP, MODEL_SHORT_NAME

MODEL_PATH = MODEL_NAME
PORT = int(os.environ.get("PORT", "8000"))

base_model = None
infer_model = None
tokenizer = None
adapter_lock = Lock()
model_lock = Lock()
active_adapter = {"id": None, "name": "基座模型"}
current_model_path = MODEL_PATH


def _get_infer_model():
    """评测任务获取当前推理模型与 tokenizer 的回调。"""
    ok, err = ensure_model_loaded()
    if not ok:
        return None, None
    return infer_model, tokenizer

_prepare_proc = None
_prepare_lock = Lock()


def _load_model(path):
    """按 config.QUANTIZATION 加载模型与 tokenizer，返回 (model, tokenizer)。"""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    kwargs = {"device_map": DEFAULT_DEVICE_MAP}
    if QUANTIZATION == "4bit":
        from transformers import BitsAndBytesConfig
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
    elif QUANTIZATION == "8bit":
        from transformers import BitsAndBytesConfig
        kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
    else:
        # none：4090(cap>=8) 用 bf16，老卡 fp16
        dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.get_device_capability()[0] >= 8 else torch.float16
        kwargs["torch_dtype"] = dtype
    tok = AutoTokenizer.from_pretrained(path)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    m = AutoModelForCausalLM.from_pretrained(path, **kwargs)
    m.eval()
    return m, tok


def ensure_model_loaded():
    global base_model, infer_model, tokenizer
    with model_lock:
        if base_model is not None:
            return True, ""
        try:
            print(f"首次加载模型（{QUANTIZATION}）：{current_model_path}", flush=True)
            m, tok = _load_model(current_model_path)
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
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass


def reload_infer_model():
    global base_model, infer_model, active_adapter, tokenizer
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
        base_model, tok = _load_model(current_model_path)
        if tokenizer is None:
            tokenizer = tok
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
    return {"status": "ok", "model": MODEL_SHORT_NAME, "quant": QUANTIZATION, "ready": infer_model is not None}


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
async def upload_dataset(file: UploadFile = File(...), domain: str = Form(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".csv", ".txt", ".json", ".jsonl"):
        return {"error": "仅支持 csv/txt/json/jsonl 格式"}
    dataset_id = f"ds-{uuid.uuid4().hex[:8]}"
    save_path = os.path.join(training.DATASET_DIR, f"{dataset_id}_{file.filename}")
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        from data_pipeline import inspect
        s, err = inspect(domain, [save_path])
        if err:
            return {"datasetId": dataset_id, "filename": file.filename, "error": err}
        return {
            "datasetId": dataset_id,
            "filename": file.filename,
            "size": os.path.getsize(save_path),
            "kept": s.kept,
            "dropped": s.dropped,
            "typeCounts": s.type_counts,
        }
    except Exception as e:
        return {"datasetId": dataset_id, "filename": file.filename, "error": str(e)}


class ProcessRequest(BaseModel):
    datasetId: str
    domain: str


@app.post("/api/datasets/process")
async def process_dataset(req: ProcessRequest):
    files = [f for f in os.listdir(training.DATASET_DIR) if f.startswith(req.datasetId + "_")]
    if not files:
        return {"error": "数据集不存在，请先上传"}
    dataset_path = os.path.join(training.DATASET_DIR, files[0])
    try:
        from data_pipeline import run_pipeline
        s = run_pipeline(req.domain, [dataset_path])
        return {
            "total": s.total,
            "kept": s.kept,
            "dropped": s.dropped,
            "typeCounts": s.type_counts,
            "outputFiles": [os.path.basename(f) for f in s.output_files],
            "preview": s.preview,
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/datasets/output/{filename}")
async def get_output_file(filename: str):
    from config import DATA_DIR
    if ".." in filename or "/" in filename or "\\" in filename:
        return {"error": "非法文件名"}
    path = DATA_DIR / filename
    if not path.exists() or not path.is_file():
        return {"error": "文件不存在"}
    return {"filename": filename, "content": path.read_text(encoding="utf-8")}


@app.get("/api/datasets/reference")
async def reference_datasets(domain: str):
    """领域参考数据集列表（从 data/reference/{slug}/manifest.json 读取）。
    框架：每个领域一个 manifest.json，描述其参考数据集元信息；
    后期扩展只需放数据 + 更新 manifest，前端自动展示。"""
    from config import DOMAIN_SLUGS, DATA_DIR
    slug = DOMAIN_SLUGS.get(domain)
    if not slug:
        return {"datasets": []}
    manifest_path = DATA_DIR / "reference" / slug / "manifest.json"
    if not manifest_path.exists():
        return {"datasets": []}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {"datasets": data.get("datasets", [])}
    except Exception as e:
        return {"error": str(e), "datasets": []}


def _scan_prepare_status():
    """扫描 data/reference/*/manifest.json，返回各数据集结果文件就绪情况。"""
    from config import DATA_DIR
    ready, missing = [], []
    ref_root = DATA_DIR / "reference"
    if not ref_root.exists():
        return ready, missing
    for manifest in sorted(ref_root.glob("*/manifest.json")):
        domain = manifest.parent.name
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            continue
        for ds in data.get("datasets", []):
            item = {"domain": domain, "id": ds.get("id", ""), "name": ds.get("name", "")}
            if (manifest.parent / ds["file"]).exists():
                ready.append(item)
            else:
                missing.append(item)
    return ready, missing


@app.post("/api/datasets/prepare")
async def prepare_reference_datasets():
    """异步触发 prepare_datasets.py 补齐缺失的结果文件。已在跑则直接返回。"""
    global _prepare_proc
    from config import PROJECT_ROOT
    with _prepare_lock:
        if _prepare_proc is not None and _prepare_proc.poll() is None:
            return {"status": "running"}
        script = PROJECT_ROOT / "scripts" / "prepare_datasets.py"
        if not script.exists():
            return {"status": "error", "error": "prepare_datasets.py 不存在"}
        _prepare_proc = subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return {"status": "running"}


@app.get("/api/datasets/prepare/status")
async def prepare_status():
    """查询结果数据准备状态：进程状态 + 各数据集就绪/缺失。"""
    global _prepare_proc
    with _prepare_lock:
        if _prepare_proc is None:
            proc_status = "idle"
        elif _prepare_proc.poll() is None:
            proc_status = "running"
        elif _prepare_proc.returncode == 0:
            proc_status = "done"
        else:
            proc_status = "error"
    ready, missing = _scan_prepare_status()
    return {"status": proc_status, "ready": ready, "missing": missing}


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
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass
        from peft import PeftModel
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
    from transformers import TextIteratorStreamer
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


# —— 评测接口 ——
class EvalRequest(BaseModel):
    name: str = ""
    adapterId: str | None = None
    use_cot: bool = True
    batchSize: int = 1
    nShot: int = 0
    testPath: str = ""
    answerPath: str = ""
    valPath: str = ""


@app.post("/api/eval")
async def start_eval(req: EvalRequest):
    """启动评测任务。adapter 切换由前端先调 /api/adapters/load 完成，此处用当前 infer_model。"""
    ok, err = ensure_model_loaded()
    if not ok:
        return {"error": f"模型加载失败：{err}"}
    if infer_model is None:
        return {"error": "模型尚未就绪，请先在对话页加载或切换权重"}
    task_id = f"ev-{uuid.uuid4().hex[:8]}"
    test_path = req.testPath or str(DEFAULT_TEST_PATH)
    answer_path = req.answerPath or str(DEFAULT_ANSWER_PATH)
    val_path = req.valPath or None
    adapter_label = active_adapter.get("name", "基座模型")
    evaluation.start_job(
        task_id,
        _get_infer_model,
        test_path,
        answer_path,
        req.use_cot,
        req.batchSize,
        dict(DEFAULT_GEN_CONFIG),
        req.adapterId,
        adapter_label,
        req.name or f"评测-{adapter_label}",
        req.nShot,
        val_path,
    )
    return {"taskId": task_id, "name": req.name or f"评测-{adapter_label}"}


@app.get("/api/eval/jobs")
def list_eval_jobs():
    return evaluation.list_jobs()


@app.get("/api/eval/{task_id}/status")
async def eval_status(task_id: str):
    return evaluation.get_status(task_id)


@app.get("/api/eval/{task_id}/result")
async def eval_result(task_id: str):
    return evaluation.get_result(task_id)


@app.post("/api/eval/{task_id}/stop")
def stop_eval(task_id: str):
    ok = evaluation.stop_job(task_id)
    return {"ok": ok} if ok else {"error": "任务不存在"}


@app.delete("/api/eval/{task_id}")
def delete_eval(task_id: str):
    evaluation.delete_job(task_id)
    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=PORT, reload=True)