# 多领域大模型训练与评测平台

## Project Handoff Summary

Project path:

```text
D:\新建文件夹\School\Tahun 4\Short-Sem\frontend
```

This project is a Vite + React + TypeScript frontend with a partially implemented Python backend for a multi-domain LLM platform.

Supported domains:

```text
medical / 医疗
legal / 法律
finance / 金融
education / 教育
```

## Original Repository State

The repository originally contained only a frontend:

- React/Vite/TypeScript UI
- Mock datasets, models, training tasks, chat replies, evaluations, and comparison results
- API contract documentation in `API.md`
- No backend
- No database
- No real model training
- No real model inference
- No real evaluation

The main mock-data file is:

```text
src/data/mock.ts
```

## Added Files

### Backend

```text
backend/app/__init__.py
backend/app/main.py
backend/app/training.py
backend/app/inference.py
backend/requirements.txt
backend/README.md
backend/.gitignore
backend/scripts/convert_cmb.py
```

### Frontend

```text
src/api.ts
src/vite-env.d.ts
```

### Documentation

```text
IMPLEMENTATION_PLAN.md
PROJECT_HANDOFF.md
```

## Real Dataset Processing

The backend now supports real:

- `.json`
- `.jsonl`
- `.csv`

Dataset functionality includes:

- Actual file storage
- SQLite dataset records
- Actual record counting
- Domain-specific storage
- Normalization into `instruction/input/output`
- Invalid-record removal
- Empty question/answer validation
- Exact duplicate detection using SHA-256
- Short-record filtering
- Reproducible shuffling with seed `42`
- Train/validation/test split generation

Generated files:

```text
train.jsonl
validation.jsonl
test.jsonl
```

Processing statistics stored in SQLite:

```text
original_count
cleaned_count
duplicate_count
invalid_count
filtered_count
final_count
```

The frontend dataset page now:

- Uploads files using `FormData`
- Starts processing automatically
- Polls the processing job
- Loads real datasets from the backend
- Displays actual processing counts
- Shows processing errors
- Resets the file input so the same file can be selected again

Main file:

```text
src/pages/Datasets.tsx
```

## CMB Medical Dataset Converter

The converter is located at:

```text
backend/scripts/convert_cmb.py
```

It supports:

- CMB Exam records
- CMB multiple-choice options
- CMB Clinical `QA_pairs`
- Conversion to normalized JSONL
- Duplicate removal
- Small subsets using `--limit`

Example:

```powershell
cd "D:\新建文件夹\School\Tahun 4\Short-Sem\frontend\backend"
python scripts\convert_cmb.py ..\CMB\data\extracted cmb-medical.jsonl --limit 100
```

The converter creates records like:

```json
{"instruction":"患者可能患有什么疾病？\nA. 选项 A\nB. 选项 B","input":"","output":"D"}
```

For CMB clinical cases, each `QA_pairs` item becomes a separate training record.

## Backend Routes Implemented

Routes are defined in:

```text
backend/app/main.py
```

Current routes:

```text
GET  /api/v1/health

GET  /api/v1/domains/{domain}/datasets
POST /api/v1/domains/{domain}/datasets
POST /api/v1/datasets/{dataset_id}/process
GET  /api/v1/processing/{job_id}
GET  /api/v1/datasets/{dataset_id}/pipeline

POST /api/v1/training/start
GET  /api/v1/training/{job_id}
GET  /api/v1/domains/{domain}/training/tasks

GET  /api/v1/domains/{domain}/models

POST /api/v1/domains/{domain}/chat/sessions
POST /api/v1/chat/sessions/{conversation_id}/messages
GET  /api/v1/chat/sessions/{conversation_id}/messages

POST /api/v1/domains/{domain}/evaluations
GET  /api/v1/domains/{domain}/evaluations

GET /api/v1/compare
```

## Real Training Backend

`backend/app/training.py` contains a Transformers + PEFT/LoRA worker.

It is designed to:

- Load a real base model
- Load processed JSONL data
- Tokenize records
- Apply LoRA
- Run Hugging Face `Trainer`
- Record training progress and loss
- Save checkpoints
- Save adapter weights
- Register model metadata only after saving succeeds

Required dependencies include:

```text
torch
transformers
peft
accelerate
```

## Real Inference Backend

`backend/app/inference.py` contains model-loading and text-generation logic.

It is designed to:

- Load a real base model
- Load a saved PEFT adapter
- Maintain conversation history
- Generate real responses
- Calculate token-level F1 for evaluation

SQLite tables were added for:

- Models
- Conversations
- Messages
- Evaluations

## Real Evaluation Backend

The evaluation worker calculates:

- Exact-match accuracy
- Token F1
- Overall score

Current overall-score formula:

```text
overall = (accuracy + f1) / 2
```

Evaluation results are stored in SQLite, and the comparison endpoint reads completed stored results.

## Frontend Integration Status

### Connected to the real backend

- Dataset upload
- Dataset processing
- Training form submission
- Training task loading
- Chat model loading
- Chat message submission
- Evaluation task submission

### Still requiring work

The following areas may still contain mock or incomplete behavior:

- `src/data/mock.ts` is still used by Overview, DomainSelect, Admin, and some fallback UI.
- Chat session creation is only partially implemented.
- Chat model selection is not fully exposed.
- Evaluation historical results and charts still use mock bundle data.
- Compare page still reads `getBundle()` and mock evaluation results.
- Training progress polling is not fully implemented in the UI.
- Real loss curves are not yet retrieved from the backend.
- Dataset version entities are simplified.
- Authentication is still simulated with `sessionStorage`.
- Admin data is still hardcoded.
- Domain list is still frontend-defined.
- ShareGPT and Alpaca conversion are not separate selectable formats.

## Important Training Issue

The old message:

```text
任务 eccdff9a-49a6-4b4c-9cc7-2a49383a4ddb 于 2026-08-21 16:37 失败：GPU 显存不足（OOM）。
```

came from the original mock task in `src/data/mock.ts`.

Search for this text and remove any remaining fallback usage if it still appears:

```text
GPU 显存不足
eccdff9a-49a6-4b4c-9cc7-2a49383a4ddb
```

The Training page should show only real backend jobs and actual `error_message` values.

## Environment

Previously detected:

```text
Python 3.11.9
PyTorch 2.9.0+cpu
CUDA available: False
NVIDIA GeForce RTX 4060 Laptop GPU
Approximately 8 GB GPU memory
```

The GPU exists, but the installed PyTorch package is CPU-only. Practical training requires a CUDA-enabled PyTorch installation.

A previous training attempt also reported:

```text
Your currently installed version of Keras is Keras 3, but this is not yet supported in Transformers.
Please install the backwards-compatible tf-keras package
```

The code attempts to disable TensorFlow loading with:

```python
TRANSFORMERS_NO_TF=1
```

This must be retested with an actual base model.

## Validation Already Completed

These checks passed previously:

```powershell
npm run build
```

```powershell
npx tsc -b --pretty false
```

```powershell
python -m py_compile backend\app\main.py backend\app\training.py backend\app\inference.py
```

```powershell
python -m py_compile backend\scripts\convert_cmb.py
```

Backend health endpoint:

```text
GET http://127.0.0.1:8000/api/v1/health
```

Returned:

```json
{"status":"ok"}
```

A real data test used five records and produced:

```text
original_count: 5
cleaned_count: 2
duplicate_count: 1
invalid_count: 2
filtered_count: 0
final_count: 2
status: COMPLETED
```

Generated output was written under:

```text
backend/storage/processed/medical/<dataset-id>/v1.0.0/
```

## Run Commands

### Backend

```powershell
cd "D:\新建文件夹\School\Tahun 4\Short-Sem\frontend\backend"
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Backend URL:

```text
http://localhost:8000
```

Health check:

```text
http://localhost:8000/api/v1/health
```

### Frontend

Open another terminal:

```powershell
cd "D:\新建文件夹\School\Tahun 4\Short-Sem\frontend"
npm run dev
```

Frontend URL:

```text
http://localhost:5173
```

Alternative frontend URL:

```text
http://127.0.0.1:5173
```

## Current Accurate Status

The project currently has:

```text
Real upload
→ Real parsing
→ Real cleaning
→ Real deduplication
→ Real filtering
→ Real dataset splitting
→ Real training API
→ Real adapter-loading API
→ Real chat API
→ Real evaluation API
→ Real comparison API
```

But the entire acceptance pipeline has not yet been demonstrated successfully because:

- Mock fallback/UI data still exists
- CUDA-enabled PyTorch is not installed
- No successful real LoRA training has been completed
- No complete real chat/evaluation run has been demonstrated
- Some frontend pages are not fully connected to live backend results

## Recommended Next Steps

1. Remove all remaining mock task/evaluation/chat displays.
2. Add complete training progress polling and real loss-curve retrieval.
3. Fully connect Chat to persisted real sessions and models.
4. Fully connect Evaluation to live evaluation records.
5. Fully connect Compare to stored database evaluation results.
6. Configure CUDA-enabled PyTorch or use a small CPU-compatible model.
7. Configure a real base model path or Hugging Face model ID.
8. Run one complete medical CMB pipeline end to end.
9. Repeat for legal, finance, and education when hardware and time allow.
