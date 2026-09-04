import json
import os

import pandas as pd


TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "utf-16")


def _read_text(path):
    last_error = None
    for encoding in TEXT_ENCODINGS:
        try:
            with open(path, "r", encoding=encoding) as file:
                return file.read()
        except UnicodeDecodeError as error:
            last_error = error
    raise ValueError(f"无法识别文件编码，请将文件另存为 UTF-8：{last_error}")


def _normalize(sample):
    if not isinstance(sample, dict):
        return None
    if sample.get("question") is not None and sample.get("options") is not None:
        options = sample.get("options")
        if isinstance(options, dict):
            option_lines = [f"{key}. {value}" for key, value in options.items()]
            option_map = {str(key): str(value) for key, value in options.items()}
        elif isinstance(options, list):
            option_lines = [f"{index + 1}. {value}" for index, value in enumerate(options)]
            option_map = {str(index + 1): str(value) for index, value in enumerate(options)}
        else:
            option_lines = []
            option_map = {}
        answer_key = sample.get("answer_idx") or sample.get("answerKey") or sample.get("label")
        answer = sample.get("answer") or sample.get("correct_answer")
        if answer_key is not None and str(answer_key) in option_map:
            answer = option_map[str(answer_key)]
        if answer is None:
            return None
        question = str(sample.get("question") or "").strip()
        input_text = question
        if option_lines:
            input_text += "\n" + "\n".join(option_lines)
        return {
            "instruction": "请回答以下医学选择题，并给出正确选项：",
            "input": input_text,
            "output": str(answer),
        }
    if sample.get("text"):
        return {"instruction": str(sample["text"]), "input": "", "output": ""}
    def first_value(keys):
        return next((sample[key] for key in keys if sample.get(key) is not None), None)

    instruction = first_value(("instruction", "prompt"))
    input_value = first_value(("input", "context", "context_text"))
    output = first_value(("output", "completion", "answer", "response", "answer_text", "回答", "答案", "回复"))
    if sample.get("ask") is not None and sample.get("answer") is not None:
        department = str(sample.get("department") or "医疗")
        instruction = f"现在你是{department}医生，请根据患者的问题给出建议："
        input_value = sample.get("ask")
        output = sample.get("answer")
        if sample.get("title"):
            input_value = f"{sample['title']}\n{input_value}"
    elif instruction is None:
        question = first_value(("question", "title", "问题", "问题描述", "query", "question_text", "内容", "用户问题"))
        if question is not None:
            instruction = "请根据以下问题给出准确回答："
            if input_value is None:
                input_value = question
    if instruction is None and output is None:
        instruction = input_value
        output = first_value(("label", "target", "result", "completion_text"))
    if instruction is None or output is None:
        return None
    item = {
        "instruction": str(instruction),
        "input": str(input_value or ""),
        "output": str(output),
    }
    return item


def parse_dataset(path):
    ext = os.path.splitext(path)[1].lower()
    raw = []
    if ext == ".jsonl":
        for line in _read_text(path).splitlines():
            line = line.strip()
            if line:
                raw.append(json.loads(line))
    elif ext == ".json":
        data = json.loads(_read_text(path))
        if isinstance(data, dict):
            data = data.get("data") or data.get("train") or data.get("samples") or []
        raw = list(data)
    elif ext == ".csv":
        csv_text = _read_text(path)
        from io import StringIO
        df = pd.read_csv(StringIO(csv_text))
        raw = df.to_dict(orient="records")
    elif ext == ".txt":
        for line in _read_text(path).splitlines():
            line = line.rstrip("\n")
            if not line.strip():
                continue
            if "\t" in line:
                q, a = line.split("\t", 1)
                raw.append({"instruction": q, "output": a})
            else:
                raw.append({"text": line})
    else:
        raise ValueError(f"不支持的数据集格式：{ext}（支持 csv/txt/json/jsonl）")

    samples = []
    for s in raw:
        item = _normalize(s)
        if item:
            samples.append(item)
    if not samples:
        raise ValueError("未解析到有效样本，请确认字段包含 instruction/output（或 prompt/completion、question/answer、text）")
    return samples


DOMAIN_RULES = {
    "medical": {
        "keywords": ("医疗", "医学", "患者", "病人", "症状", "诊断", "治疗", "药物", "medical", "patient", "hypertension", "blood pressure", "disease", "treatment"),
        "risky": ("包治", "绝对治愈", "百分之百治愈"),
        "label": "medical",
    },
    "legal": {
        "keywords": ("法律", "合同", "诉讼", "法条", "律师", "法院", "legal", "contract"),
        "risky": ("百分之百胜诉", "保证胜诉", "绝对合法"),
        "label": "legal",
    },
    "finance": {
        "keywords": ("金融", "投资", "股票", "基金", "贷款", "利率", "财务", "finance", "investment"),
        "risky": ("稳赚不赔", "保证收益", "零风险", "绝对赚钱"),
        "label": "finance",
    },
    "education": {
        "keywords": ("教育", "学生", "课程", "考试", "学习", "教师", "education", "student"),
        "risky": ("保证满分", "百分之百通过", "绝对正确"),
        "label": "education",
    },
}


def _annotation_for(sample, domain):
    text = " ".join(str(sample.get(key, "")) for key in ("instruction", "input", "output", "text")).lower()
    if any(word in text for word in ("why", "为什么", "原因", "how", "如何", "怎样")):
        category = "reasoning"
    elif any(word in text for word in ("summarize", "summary", "总结", "概括")):
        category = "summarization"
    elif any(word in text for word in ("translate", "翻译")):
        category = "translation"
    else:
        category = "qa"
    rule = DOMAIN_RULES.get(domain)
    domain_match = bool(rule and any(word.lower() in text for word in rule["keywords"]))
    return {"domain": domain or "general", "category": category, "domainMatch": domain_match, "source": "rule-based"}


def clean_and_annotate(samples, domain="", min_length=2, max_length=12000):
    """Clean normalized samples and add reproducible rule-based annotations."""
    stats = {
        "input": len(samples),
        "blank": 0,
        "duplicate": 0,
        "tooShort": 0,
        "tooLong": 0,
        "domainRisk": 0,
    }
    cleaned = []
    seen = set()

    for sample in samples:
        item = {key: value.strip() if isinstance(value, str) else value for key, value in sample.items()}
        if "text" in item and item.get("text"):
            item = {"instruction": str(item["text"]), "input": "", "output": ""}
        else:
            item = {
                "instruction": str(item.get("instruction", "")).strip(),
                "input": str(item.get("input", "")).strip(),
                "output": str(item.get("output", "")).strip(),
            }
        content = " ".join(str(item.get(key, "")) for key in ("instruction", "input", "output", "text")).strip()
        if not content:
            stats["blank"] += 1
            continue
        if len(content) < min_length:
            stats["tooShort"] += 1
            continue
        if len(content) > max_length:
            stats["tooLong"] += 1
            continue
        rule = DOMAIN_RULES.get(domain)
        if rule and any(word.lower() in content.lower() for word in rule["risky"]):
            stats["domainRisk"] += 1
            continue

        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key in seen:
            stats["duplicate"] += 1
            continue
        seen.add(key)
        cleaned.append(item)

    stats["output"] = len(cleaned)
    stats["filtered"] = stats["input"] - stats["output"]
    stats["quality"] = round((stats["output"] / stats["input"]) * 100, 1) if stats["input"] else 0
    return cleaned, stats