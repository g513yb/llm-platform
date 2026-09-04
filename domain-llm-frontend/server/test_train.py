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
        BASE + "/api/datasets/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode())


print("== 上传数据集 ==")
r = upload(DATASET)
print(json.dumps(r, ensure_ascii=False))
if "error" in r:
    raise SystemExit("上传失败")
dsid = r["datasetId"]

print("\n== 启动训练 ==")
req = urllib.request.Request(
    BASE + "/api/train",
    data=json.dumps(
        {"name": "test-run", "datasetId": dsid, "rank": 8, "lr": "2e-4", "epochs": 2, "batch": 2}
    ).encode(),
    headers={"Content-Type": "application/json"},
)
tr = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
print(json.dumps(tr, ensure_ascii=False))
tid = tr["taskId"]

print("\n== 轮询状态 ==")
for _ in range(180):
    s = json.loads(
        urllib.request.urlopen(f"{BASE}/api/train/{tid}/status", timeout=10).read().decode()
    )
    print(f"status={s['status']} progress={s['progress']} loss={s.get('loss')} msg={s.get('message','')[:70]}", flush=True)
    if s["status"] in ("完成", "失败"):
        print("loss_history:", s.get("loss_history"))
        print("adapter:", s.get("adapter_path"))
        break
    time.sleep(2)