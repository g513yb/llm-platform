"""CMB-Exam 选择题评测核心逻辑（移植自 tests/fixtures/_downloads/CMB）。

完整重现 CMB 的 12 项处理细节：
  ① option_str 用 len(v)>1 过滤空/单字符选项
  ② prompt 两步 format（instruction 套 question 模板）
  ③ tokenizer padding_side='left'
  ④ lengths = input_ids.shape[1]（padding 后统一长度）
  ⑤ 切 [lengths:] 去 prompt（依赖左 padding 右对齐）
  ⑥ num_return_sequences 分组归并
  ⑦ 单项/C型题抽多字母时取 choice[0]
  ⑧ 多采样投票取最多
  ⑨ match_choice 正则失败回退"取全文 A-G"
  ⑩ do_sample=True 且 num_return_sequences>1 时强制降为 1（cot_flag 双分支相同，已合并）
  ⑪ 父类准确率 = 子类准确率算术平均（非总数比）
  ⑫ 多项选择题字符串 == 比对（如 "ABD"）
"""
from __future__ import annotations

import json
import random
import re
from collections import defaultdict
from pathlib import Path


# —— 评测数据默认路径（CMB-test，11200 题，已入库 data/reference/medical/eval/）——
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEST_PATH = PROJECT_ROOT / "data" / "reference" / "medical" / "eval" / "cmb_test_choice_question.json"
DEFAULT_ANSWER_PATH = PROJECT_ROOT / "data" / "reference" / "medical" / "eval" / "cmb_test_choice_answer.json"
DEFAULT_VAL_PATH = PROJECT_ROOT / "data" / "reference" / "medical" / "eval" / "cmb_val_merge.json"

# —— prompt 模板（原样搬自 CMB base.py query_prompt_1/2）——
SYSTEM_PROMPT = "你是一个医学考试助手。"
QUESTION_TEMPLATE_COT = "以下是中国{exam_type}中{exam_class}考试的一道{question_type}，请分析每个选项，并最后给出答案。\n{question}\n{option_str}"
QUESTION_TEMPLATE_DIRECT = "以下是中国{exam_type}中{exam_class}考试的一道{question_type}，不需要做任何分析和解释，直接输出答案选项。\n{question}\n{option_str}"

# —— 生成默认参数（搬自 CMB configs/model_config.yaml）——
DEFAULT_GEN_CONFIG = dict(max_new_tokens=512, min_new_tokens=1, do_sample=False, num_return_sequences=1)

# —— 答案抽取 ——
_OPTIONS = ["A", "B", "C", "D", "E", "F", "G"]
_ANS_RE = re.compile(r"(答案|正确选项)(?:是|：|为|应该是|应该为)(.*?)(。|\.|$)", re.S)


def load_test_data(test_path: str | Path = DEFAULT_TEST_PATH,
                   answer_path: str | Path = DEFAULT_ANSWER_PATH) -> list[dict]:
    """加载 CMB-test 题目并按 id 合并答案（ground truth）。"""
    questions = json.loads(Path(test_path).read_text(encoding="utf-8"))
    answers = json.loads(Path(answer_path).read_text(encoding="utf-8"))
    ans_map = {a["id"]: a["answer"] for a in answers}
    out = []
    for q in questions:
        item = dict(q)
        item["answer"] = ans_map.get(q["id"], "")
        out.append(item)
    return out


def build_option_str(option: dict) -> str:
    """① len(v)>1 过滤空/单字符选项。"""
    return "\n".join(f"{k}. {v}" for k, v in option.items() if len(v) > 1)


def build_user_prompt(item: dict, use_cot: bool) -> str:
    """② 构造 user 消息内容（中文考试模板，两步 format 的内层）。

    返回纯文本，由调用方套 Qwen chat template（替换 CMB 的"问：/答："）。
    """
    option_str = build_option_str(item["option"])
    template = QUESTION_TEMPLATE_COT if use_cot else QUESTION_TEMPLATE_DIRECT
    return template.format(
        exam_type=item["exam_type"],
        exam_class=item["exam_class"],
        question_type=item["question_type"],
        question=item["question"],
        option_str=option_str,
    )


def build_chat_messages(item: dict, use_cot: bool,
                        fewshot_examples: list[dict] | None = None) -> list[dict]:
    """构造 Qwen chat messages（system + fewshot user/assistant 对 + user），供 apply_chat_template。

    few-shot 在 chat model 里的标准做法：把示例作为多轮对话历史拼进 messages，
    替换 CMB 的"问：/答："文本拼接（base.py fewshot_template）。
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if fewshot_examples:
        for ex in fewshot_examples:
            messages.append({"role": "user", "content": build_user_prompt(ex, use_cot)})
            # 搬自 base.py:214/216：CoT 用 explanation+结论，Direct 只给答案
            if use_cot:
                gpt = f"{ex.get('explanation', '')}所以答案是{ex['answer']}。"
            else:
                gpt = f"答案是{ex['answer']}。"
            messages.append({"role": "assistant", "content": gpt})
    messages.append({"role": "user", "content": build_user_prompt(item, use_cot)})
    return messages


def load_val_data(val_path: str | Path = DEFAULT_VAL_PATH) -> list[dict]:
    """加载 CMB-val（280 题，带 explanation + answer）作 few-shot 示例库。"""
    return json.loads(Path(val_path).read_text(encoding="utf-8"))


def select_fewshot_examples(val_data: list[dict], item: dict, n_shot: int,
                            rng: random.Random) -> list[dict]:
    """按 exam_type/exam_class 精确匹配随机选 n 条（搬自 generate_fewshot.py:25-39）。

    不足 n 条时取全部可用（CMB 原始代码 raise ValueError，此处改为鲁棒降级）。
    """
    candidates = [
        v for v in val_data
        if v["exam_type"] == item["exam_type"] and v["exam_class"] == item["exam_class"]
    ]
    if len(candidates) <= n_shot:
        return candidates
    return rng.sample(candidates, n_shot)


def match_choice(text: str) -> str:
    """⑨ 正则匹配"答案是A"→ 失败回退取全文 A-G。⑩ cot_flag 双分支相同，已合并。"""
    m = _ANS_RE.search(text)
    if m:
        return "".join(x for x in m.group(2) if x in _OPTIONS)
    return "".join(i for i in text if i in _OPTIONS)


def extract_ans(answers: list[str], question_type: str) -> str:
    """⑥⑦⑧ 多次采样投票。

    answers: 该题的 num_return_sequences 个模型输出文本。
    """
    ress: dict[str, int] = defaultdict(int)
    for res in answers:
        choice = match_choice(res)
        # ⑦ 单项/C型题抽多字母时只取首字母；多项选择题保留全字母
        if len(choice) > 1 and question_type != "多项选择题":
            choice = choice[0]
        if len(choice) > 0:
            ress[choice] += 1
    if not ress:
        return ""
    # ⑧ 投票取最多
    return max(ress.items(), key=lambda x: x[1])[0]


def normalize_gen_config(gen_config: dict) -> dict:
    """⑩ do_sample=True 且 num_return_sequences>1 时强制降为 1（HF 限制）。"""
    cfg = dict(gen_config)
    if cfg.get("num_return_sequences") is None:
        cfg["num_return_sequences"] = 1
    elif cfg.get("num_return_sequences", 1) > 1 and cfg.get("do_sample", False):
        cfg["num_return_sequences"] = 1
    if cfg.get("pad_token_id") is None:
        # 调用方应传入，兜底
        pass
    return cfg


def run_inference_batch(model, tokenizer, prompts: list[str], gen_config: dict) -> list[list[str]]:
    """③④⑤⑥ batch 推理。

    返回：每题一组（num_return_sequences 个）解码文本。
    """
    import torch
    # ③ 左 padding，保证切 prompt 时右对齐
    orig_padding_side = tokenizer.padding_side
    tokenizer.padding_side = "left"
    try:
        inputs = tokenizer(prompts, padding=True, truncation=True, return_tensors="pt").to(model.device)
        # ④ padding 后统一长度
        lengths = inputs.input_ids.shape[1]
        n_ret = gen_config.get("num_return_sequences", 1)
        with torch.no_grad():
            outputs = model.generate(**inputs, **gen_config)
        results: list[list[str]] = []
        batch_return: list[str] = []
        for i in range(len(outputs)):
            # ⑤ 切 [lengths:] 去 prompt+left-padding
            gen = outputs[i][lengths:]
            text = tokenizer.decode(gen, skip_special_tokens=True)
            batch_return.append(text)
            # ⑥ 每 n_ret 条归为一组
            if i % n_ret == n_ret - 1:
                results.append(batch_return)
                batch_return = []
        return results
    finally:
        tokenizer.padding_side = orig_padding_side


def score_layered(items: list[dict], wrong_limit: int = 200) -> dict:
    """⑪⑫ 分层准确率。

    items: 每条含 id/exam_type/exam_class/question_type/answer(真值)/model_answer。
    返回 overall/per_category/per_subcategory/correct/total/wrong_items。
    wrong_items 截断前 wrong_limit 条避免结果文件过大。
    """
    stats: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {"correct": 0, "total": 0}))
    correct = 0
    wrong_items = []
    for it in items:
        et, ec = it["exam_type"], it["exam_class"]
        # ⑫ 字符串 == 比对（多项选择题如 "ABD" 直接比）；空真值不算错
        is_correct = it["answer"] != "" and it["model_answer"] == it["answer"]
        stats[et][ec]["total"] += 1
        if is_correct:
            stats[et][ec]["correct"] += 1
            correct += 1
        elif len(wrong_items) < wrong_limit:
            wrong_items.append({
                "id": it.get("id"),
                "exam_type": et,
                "exam_class": ec,
                "question_type": it.get("question_type", ""),
                "gold": it["answer"],
                "pred": it["model_answer"],
            })
    # ⑪ 父类准确率 = 子类准确率算术平均
    per_sub: dict[str, dict[str, float]] = {}
    per_cat: dict[str, float] = {}
    for et, classes in stats.items():
        per_sub[et] = {}
        accs = []
        for ec, st in classes.items():
            acc = st["correct"] / st["total"] if st["total"] > 0 else 0.0
            per_sub[et][ec] = round(acc, 4)
            accs.append(acc)
        per_cat[et] = round(sum(accs) / len(accs), 4) if accs else 0.0
    overall = round(correct / len(items), 4) if items else 0.0
    return {
        "overall": overall,
        "correct": correct,
        "total": len(items),
        "per_category": per_cat,
        "per_subcategory": per_sub,
        "wrong_items": wrong_items,
        "wrong_truncated": len(wrong_items) >= wrong_limit,
    }


def composite_score(overall: float) -> int:
    """把分层准确率 overall（0-1）映射为 0-100 整数综合分。

    当前只评 CMB-Exam 选择题准确率，六维雷达图其余维度暂用 overall 填充，
    后续 Sprint 接入更多维度后再做加权。
    """
    return round(overall * 100)