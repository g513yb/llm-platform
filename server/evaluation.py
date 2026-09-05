"""评测任务管理（仿 training.py）：JOBS dict + eval_jobs.json + 线程。

复用 app.py 的 infer_model/tokenizer（通过 get_model_fn 回调），
adapter 切换由前端先调 /api/adapters/load 完成，评测任务用当前挂载的权重。
"""
import json
import os
import random
import shutil
import threading
from datetime import datetime

from eval_runner import (
    DEFAULT_ANSWER_PATH,
    DEFAULT_GEN_CONFIG,
    DEFAULT_TEST_PATH,
    DEFAULT_VAL_PATH,
    build_chat_messages,
    composite_score,
    extract_ans,
    load_test_data,
    load_val_data,
    normalize_gen_config,
    run_inference_batch,
    score_layered,
    select_fewshot_examples,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "data", "eval"))
os.makedirs(EVAL_DIR, exist_ok=True)

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
JOBS_PATH = os.path.join(BASE_DIR, "eval_jobs.json")


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
                    j["message"] = "服务重启，评测中断"
                j["stop"] = False
                JOBS[tid] = j
    except Exception:
        pass


_load_jobs()


def _set(task_id, **kw):
    with JOBS_LOCK:
        JOBS[task_id].update(kw)
    _save_jobs()


def run_eval(task_id, get_model_fn, test_path, answer_path, use_cot, batch_size, gen_config, adapter_label,
             n_shot=0, val_path=None):
    _set(task_id, status="运行中", message="正在加载评测数据……")
    try:
        items = load_test_data(test_path, answer_path)
        total = len(items)
        val_data = None
        rng = None
        if n_shot > 0:
            val_data = load_val_data(val_path or DEFAULT_VAL_PATH)
            rng = random.Random(42)
            _set(task_id, total=total, message=f"已加载 {total} 题 + {len(val_data)} 条 few-shot 示例，准备推理……")
        else:
            _set(task_id, total=total, message=f"已加载 {total} 题，准备推理……")

        model, tokenizer = get_model_fn()
        if model is None:
            raise RuntimeError("模型尚未就绪，请先在对话页加载模型或切换权重")

        cfg = normalize_gen_config(gen_config)
        if cfg.get("pad_token_id") is None and getattr(tokenizer, "pad_token_id", None) is not None:
            cfg["pad_token_id"] = tokenizer.pad_token_id

        all_items = []
        for start in range(0, total, batch_size):
            if JOBS[task_id].get("stop"):
                raise RuntimeError("用户终止评测")
            batch = items[start:start + batch_size]
            prompts = []
            for it in batch:
                fewshot = None
                if val_data is not None:
                    fewshot = select_fewshot_examples(val_data, it, n_shot, rng)
                msgs = build_chat_messages(it, use_cot, fewshot_examples=fewshot)
                p = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
                prompts.append(p)
            responses = run_inference_batch(model, tokenizer, prompts, cfg)
            for it, resp in zip(batch, responses):
                it["model_answer"] = extract_ans(resp, it.get("question_type", "单项选择题"))
                it["raw_outputs"] = resp
                all_items.append(it)
            done = min(start + batch_size, total)
            _set(task_id, progress=round(done / total * 100), message=f"已推理 {done}/{total} 题")

        _set(task_id, message="正在评分……")
        result = score_layered(all_items)
        composite = composite_score(result["overall"])

        task_dir = os.path.join(EVAL_DIR, task_id)
        os.makedirs(task_dir, exist_ok=True)
        result_path = os.path.join(task_dir, "result.json")
        answers_path = os.path.join(task_dir, "answers.jsonl")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump({
                "task_id": task_id,
                "adapter": adapter_label,
                "use_cot": use_cot,
                "test_path": str(test_path),
                "answer_path": str(answer_path),
                "composite": composite,
                "result": result,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
            }, f, ensure_ascii=False, indent=2)
        with open(answers_path, "w", encoding="utf-8") as f:
            for it in all_items:
                f.write(json.dumps({
                    "id": it.get("id"),
                    "exam_type": it["exam_type"],
                    "exam_class": it["exam_class"],
                    "question_type": it.get("question_type", ""),
                    "gold": it["answer"],
                    "pred": it["model_answer"],
                    "raw_outputs": it.get("raw_outputs", []),
                }, ensure_ascii=False) + "\n")

        _set(
            task_id,
            status="完成",
            progress=100,
            composite=composite,
            overall=result["overall"],
            correct=result["correct"],
            total=result["total"],
            result_path=result_path,
            message=f"评测完成：准确率 {result['overall'] * 100:.2f}%（{result['correct']}/{result['total']}）",
        )
    except Exception as e:
        if "用户终止" in str(e):
            _set(task_id, status="已终止", message="用户终止评测")
        else:
            _set(task_id, status="失败", message=f"{type(e).__name__}: {e}")


def start_job(task_id, get_model_fn, test_path, answer_path, use_cot, batch_size, gen_config,
              adapter_id, adapter_label, name, n_shot=0, val_path=None):
    with JOBS_LOCK:
        JOBS[task_id] = {
            "status": "等待",
            "progress": 0,
            "message": "",
            "name": name,
            "adapter": adapter_label,
            "adapterId": adapter_id,
            "use_cot": use_cot,
            "n_shot": n_shot,
            "total": 0,
            "correct": 0,
            "overall": 0,
            "composite": 0,
            "result_path": "",
            "started": datetime.now().strftime("%m-%d %H:%M"),
            "stop": False,
        }
    _save_jobs()
    t = threading.Thread(
        target=run_eval,
        args=(task_id, get_model_fn, test_path, answer_path, use_cot, batch_size, gen_config, adapter_label,
              n_shot, val_path),
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
    if job:
        task_dir = os.path.join(EVAL_DIR, task_id)
        if os.path.isdir(task_dir):
            try:
                shutil.rmtree(task_dir)
            except Exception:
                pass
    _save_jobs()
    return True


def get_status(task_id):
    with JOBS_LOCK:
        return dict(JOBS.get(task_id, {"status": "未知", "progress": 0, "message": "任务不存在"}))


def get_result(task_id):
    with JOBS_LOCK:
        job = JOBS.get(task_id)
    if not job:
        return {"error": "评测任务不存在"}
    result_path = job.get("result_path", "")
    if not result_path or not os.path.isfile(result_path):
        return {"error": "结果文件不存在（任务可能未完成）"}
    try:
        with open(result_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"error": f"读取结果失败：{e}"}