import json
import os
import time
import urllib.request
import uuid

BASE = "http://127.0.0.1:8000"
DATASET = r"D:\domain-llm-frontend\server\test_dataset.jsonl"


def upload(path):
    boundary = uuid.uuid4().hex
    filename = os.path.basename(path)
    with open(path, "rb") as f:
        data = f.read()
    body = (
        ("--" + boundary + "\r\n").encode()
        + f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
        + b"Content-Type: application/octet-stream\r\n\r\n"
        + data
        + ("\r\n--" + boundary + "--\r\n").encode()
    )
    req = urllib.request.Request(
        BASE + "/api/datasets/upload", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode())


def post(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode())


def get(url):
    return json.loads(urllib.request.urlopen(url, timeout=15).read().decode())


def chat(messages):
    req = urllib.request.Request(
        BASE + "/api/chat",
        data=json.dumps({"messages": messages, "max_new_tokens": 60}).encode(),
        headers={"Content-Type": "application/json"},
    )
    raw = urllib.request.urlopen(req, timeout=120).read().decode()
    out = ""
    for line in raw.split("\n"):
        if line.startswith("data: "):
            d = line[6:]
            if d == "[DONE]":
                continue
            try:
                out += json.loads(d)["token"]
            except Exception:
                pass
    return out


print("== 上传 + 训练 ==")
r = upload(DATASET)
print("upload:", r)
tr = post(BASE + "/api/train", {"name": "adapter-test", "datasetId": r["datasetId"], "domain": "测试", "rank": 8, "lr": "2e-4", "epochs": 1, "batch": 2})
print("train:", tr)
tid = tr["taskId"]
for _ in range(120):
    s = get(f"{BASE}/api/train/{tid}/status")
    print(f"  {s['status']} {s['progress']}% loss={s.get('loss')}")
    if s["status"] in ("完成", "失败"):
        break
    time.sleep(2)

print("\n== 权重列表 ==")
adapters = get(BASE + "/api/adapters")
print(json.dumps(adapters, ensure_ascii=False, indent=2))
if not adapters:
    raise SystemExit("无权重")

aid = adapters[-1]["id"]
print(f"\n== 加载权重 {aid} ==")
print(post(BASE + "/api/adapters/load", {"adapterId": aid}))

print("\n== 用权重对话：你好 ==")
print("回复:", chat([{"role": "user", "content": "你好"}]))

print("\n== 切回基座 ==")
print(post(BASE + "/api/adapters/load", {"adapterId": None}))
print("基座回复:", chat([{"role": "user", "content": "你好"}]))
