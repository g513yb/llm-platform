# 数据处理测试

覆盖 `server/data_pipeline` 的 12 种 schema 识别与 `run_pipeline` 全链路。单元/合成测试在 `.venv-verify`（仅 pandas/numpy）下可本地跑；真实数据集成测试需云端下载。

## 运行

### 本地（合成数据，无需下载）
```bash
PYTHONIOENCODING=utf-8 .venv-verify/Scripts/python -m pytest tests/test_readers.py -v
```
> `test_readers.py` 自带 `sys.path.insert(0, ROOT/"server")`，让 `from data_pipeline import ...` 可达（`config`/`data_pipeline` 已移入 `server/`）。

### 云端流水线（下载真实数据 → 测试 → 可视化报告）
```bash
git push origin main && ./deploy.sh datatest   # 云端一键：下载→测试→报告
./deploy.sh report                              # 端口转发浏览器查看 report.html
```
流水线 = `tests/cloud_run.sh`：`download_datasets.py --all`（幂等）→ `run_and_report.py`（自包含 HTML+JSON 报告）。下载的原始数据落 `tests/fixtures/_downloads/`，**不入库**（见 .gitignore）。

## 文件

- `test_readers.py` —— 数据处理测试：单元（`_parse_*`）+ 合成（`fixtures/synthetic/`）+ 真实数据集成（`fixtures/_downloads/`）。import 指向 `server/data_pipeline`。
- `run_and_report.py` —— unittest 运行器 + 自包含 HTML/JSON 报告（零第三方依赖）。
- `download_datasets.py` —— 数据集下载器（零第三方依赖：git/urllib；幂等/重试/镜像）。
- `cloud_run.sh` —— 云端一键流水线。
- `fixtures/synthetic/` —— 合成数据（`cmmlu.csv`、`medqa.jsonl`），入库，离线确定性。
- `fixtures/_downloads/` —— 真实数据集缓存，**不入库**（gitignore），集成测试用。
