import functools
import gc
import json
import os
import shutil
import threading
from datetime import datetime

import torch
from torch.utils.data import DataLoader, Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)

from dataset_utils import parse_dataset

MODEL_PATH = r"C:\Qwen2.5-3B-Instruct"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADAPTER_DIR = os.path.join(BASE_DIR, "adapters")
DATASET_DIR = os.path.join(BASE_DIR, "datasets")
os.makedirs(ADAPTER_DIR, exist_ok=True)
os.makedirs(DATASET_DIR, exist_ok=True)

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()

MAX_LEN = 256
INDEX_PATH = os.path.join(ADAPTER_DIR, "index.json")
JOBS_PATH = os.path.join(BASE_DIR, "jobs.json")


def _save_jobs():
    try:
        with JOBS_LOCK:
            data = {k: {kk: vv for kk, vv in v.items() if kk != "stop"} for k, v in JOBS.items()}
        with open(JOBS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_jobs():
    if not os.path.exists(JOBS_PATH):
        return
    try:
        with open(JOBS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        with JOBS_LOCK:
            for tid, j in data.items():
                if j.get("status") in ("运行中", "等待"):
                    j["status"] = "已终止"
                    j["message"] = "服务重启，训练中断"
                j["stop"] = False
                JOBS[tid] = j
    except Exception:
        pass


_load_jobs()


def register_adapter(info):
    with JOBS_LOCK:
        index = []
        if os.path.exists(INDEX_PATH):
            try:
                with open(INDEX_PATH, "r", encoding="utf-8") as f:
                    index = json.load(f)
            except Exception:
                index = []
        index.append(info)
        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)


def list_adapters():
    if not os.path.exists(INDEX_PATH):
        return []
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


class SFTDataset(Dataset):
    def __init__(self, samples, tokenizer, max_len=MAX_LEN):
        self.data = []
        for s in samples:
            try:
                ids, labels = self._build(s, tokenizer, max_len)
                if ids:
                    self.data.append((ids, labels))
            except Exception:
                continue

    def _build(self, s, tokenizer, max_len):
        if "text" in s:
            ids = tokenizer(s["text"], truncation=True, max_length=max_len)["input_ids"]
            return ids, list(ids)
        instruction = s["instruction"]
        output = s["output"]
        inp = s.get("input", "")
        user = instruction + (("\n" + inp) if inp else "")
        msgs = [{"role": "user", "content": user}, {"role": "assistant", "content": output}]
        prompt = tokenizer.apply_chat_template([msgs[0]], tokenize=False, add_generation_prompt=True)
        full = tokenizer.apply_chat_template(msgs, tokenize=False)
        prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        full_ids = tokenizer(full, add_special_tokens=False)["input_ids"]
        labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids):]
        labels = labels[: len(full_ids)]
        return full_ids, labels

    def __len__(self):
        return len(self.data)

    def __getitem__(self, i):
        return self.data[i]


def _collate(batch, pad_id):
    max_len = max(len(x[0]) for x in batch)
    input_ids, labels, attn = [], [], []
    for ids, lab in batch:
        pad = max_len - len(ids)
        input_ids.append(ids + [pad_id] * pad)
        labels.append(lab + [-100] * pad)
        attn.append([1] * len(ids) + [0] * pad)
    return {
        "input_ids": torch.tensor(input_ids, dtype=torch.long),
        "attention_mask": torch.tensor(attn, dtype=torch.long),
        "labels": torch.tensor(labels, dtype=torch.long),
    }


def _set(task_id, **kw):
    with JOBS_LOCK:
        JOBS[task_id].update(kw)
    _save_jobs()


def run_training(task_id, dataset_path, rank, lr, epochs, batch, name, domain, dataset_label, model_path, release_fn, reload_fn):
    _set(task_id, status="运行中", message="正在加载数据与模型……")
    model = None
    try:
        release_fn()
        samples = parse_dataset(dataset_path)
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        bnb = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_path, quantization_config=bnb, device_map={"": 0}
        )
        model = prepare_model_for_kbit_training(model)
        lora = LoraConfig(
            r=rank,
            lora_alpha=2 * rank,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        )
        model = get_peft_model(model, lora)
        model.train()

        ds = SFTDataset(samples, tokenizer)
        if len(ds) == 0:
            raise ValueError("数据集解析后无可用样本（可能字段不匹配）")
        accum = max(1, batch)
        loader = DataLoader(
            ds,
            batch_size=1,
            shuffle=True,
            collate_fn=functools.partial(_collate, pad_id=tokenizer.pad_token_id),
        )
        optim = torch.optim.AdamW(
            filter(lambda p: p.requires_grad, model.parameters()), lr=float(lr)
        )

        total_steps = max(1, (len(loader) * epochs) // accum)
        gstep = 0
        _set(task_id, message=f"开始训练：样本 {len(ds)} 条，等效批大小 {accum}，轮数 {epochs}")

        for _ in range(epochs):
            for bi, batch_data in enumerate(loader):
                if JOBS[task_id].get("stop"):
                    raise RuntimeError("用户终止训练")
                batch_data = {k: v.to(model.device) for k, v in batch_data.items()}
                out = model(**batch_data)
                loss = out.loss / accum
                loss.backward()
                if (bi + 1) % accum == 0:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optim.step()
                    optim.zero_grad()
                    gstep += 1
                    cur = out.loss.item()
                    _set(
                        task_id,
                        loss=round(cur, 4),
                        loss_history=JOBS[task_id]["loss_history"] + [round(cur, 4)],
                        progress=min(99, int(gstep / total_steps * 100)),
                    )

        adapter_path = os.path.join(ADAPTER_DIR, task_id)
        model.save_pretrained(adapter_path)
        tokenizer.save_pretrained(adapter_path)
        del model
        model = None
        gc.collect()
        torch.cuda.empty_cache()
        reload_fn()
        _set(
            task_id,
            status="完成",
            progress=100,
            adapter_path=adapter_path,
            message=f"训练完成，LoRA 适配器已保存至 {adapter_path}",
        )
        register_adapter({
            "id": task_id,
            "name": name,
            "domain": domain,
            "adapter_path": adapter_path,
            "loss": JOBS[task_id]["loss"],
            "samples": len(samples),
            "rank": rank,
            "lr": lr,
            "epochs": epochs,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        })
    except Exception as e:
        if model is not None:
            del model
        gc.collect()
        torch.cuda.empty_cache()
        try:
            reload_fn()
        except Exception:
            pass
        if "用户终止" in str(e):
            _set(task_id, status="已终止", message="用户终止训练")
        else:
            _set(task_id, status="失败", message=f"{type(e).__name__}: {e}")


def start_job(task_id, dataset_path, rank, lr, epochs, batch, name, domain, dataset_label, model_path, release_fn, reload_fn):
    with JOBS_LOCK:
        JOBS[task_id] = {
            "status": "等待",
            "progress": 0,
            "loss": 0,
            "loss_history": [],
            "message": "",
            "adapter_path": "",
            "name": name,
            "dataset": dataset_label,
            "domain": domain,
            "baseModel": "Qwen2.5-3B-Instruct",
            "started": datetime.now().strftime("%m-%d %H:%M"),
            "stop": False,
        }
    _save_jobs()
    t = threading.Thread(
        target=run_training,
        args=(task_id, dataset_path, rank, lr, epochs, batch, name, domain, dataset_label, model_path, release_fn, reload_fn),
        daemon=True,
    )
    t.start()


def list_jobs():
    with JOBS_LOCK:
        return [{**v, "id": k} for k, v in reversed(list(JOBS.items()))]


def stop_job(task_id):
    with JOBS_LOCK:
        if task_id in JOBS:
            JOBS[task_id]["stop"] = True
            return True
    return False


def delete_job(task_id):
    with JOBS_LOCK:
        job = JOBS.pop(task_id, None)
    if job and job.get("adapter_path") and os.path.isdir(job["adapter_path"]):
        try:
            shutil.rmtree(job["adapter_path"])
        except Exception:
            pass
    _save_jobs()
    return True


def get_status(task_id):
    with JOBS_LOCK:
        return dict(JOBS.get(task_id, {"status": "未知", "progress": 0, "loss": 0, "loss_history": [], "message": "任务不存在"}))