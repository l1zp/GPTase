# MinerU Cloud API Reference

Use this file when extracting via the MinerU cloud Precision API.

## When To Use

Prefer cloud API over local CLI whenever `MINERU_TOKEN` is set. Advantages:
- No local model downloads or GPU required
- No Apple Silicon / transformers compatibility issues
- Supports true batch processing in a single request
- Higher and more consistent extraction quality

## Authentication

### 获取 Token

1. 登录 [https://mineru.net](https://mineru.net)
2. 进入 **API → Token 管理**（直达地址：`https://mineru.net/apiManage/token`）
3. 创建或复制 Token（JWT 格式，以 `eyJ` 开头）

### 存储位置（本项目）

Token 存放在项目根目录的 `.env` 文件中（已在 `.gitignore` 中排除）：

```
MINERU_TOKEN=eyJ0eXBlIjoiSldUIi...
```

已验证可用（2026-04-21）。

### 加载方式

在脚本中用绝对路径加载，避免 `find_dotenv()` 在 heredoc/stdin 模式下报 `AssertionError`：

```python
from dotenv import load_dotenv
import os

load_dotenv("/Users/ryanxu/CodeBase/GPTase/.env")  # 用绝对路径，stdin 调用时更稳定
TOKEN = os.environ["MINERU_TOKEN"]
```

或在 shell 中导出：

```bash
export $(grep MINERU_TOKEN /Users/ryanxu/CodeBase/GPTase/.env | xargs)
```

验证：`echo $MINERU_TOKEN` 应打印非空 JWT。

## API Endpoints

| Action | Method | URL |
|--------|--------|-----|
| Get pre-signed upload URLs | POST | `https://mineru.net/api/v4/file-urls/batch` |
| Poll extraction results | GET | `https://mineru.net/api/v4/extract-results/batch/{batch_id}` |

Headers for all requests:
```json
{"Authorization": "Bearer <TOKEN>", "Content-Type": "application/json"}
```

## Correct Flow (3 steps)

### Step 1 — Get pre-signed upload URLs

```python
import requests, os

HEADERS = {
    "Authorization": f"Bearer {os.environ['MINERU_TOKEN']}",
    "Content-Type": "application/json",
}

files_meta = [
    {"name": "paper.pdf", "is_ocr": False, "data_id": "paper"},
]
r = requests.post(
    "https://mineru.net/api/v4/file-urls/batch",
    headers=HEADERS,
    json={"files": files_meta},
)
r.raise_for_status()
batch_id   = r.json()["data"]["batch_id"]
signed_url = r.json()["data"]["file_urls"][0]
```

`batch_id` is used for **both** upload and polling — there is no separate submit step.

### Step 2 — Upload files (no Content-Type header)

```python
# CRITICAL: do NOT set Content-Type when uploading to OSS pre-signed URLs.
# Adding Content-Type breaks the request signature and returns 403.
with open("paper.pdf", "rb") as f:
    resp = requests.put(signed_url, data=f)
resp.raise_for_status()
```

### Step 3 — Poll and download

```python
import time, zipfile
from pathlib import Path

def poll_and_save(batch_id, output_dir, interval=10):
    url = f"https://mineru.net/api/v4/extract-results/batch/{batch_id}"
    while True:
        r = requests.get(url, headers=HEADERS)
        results = r.json()["data"]["extract_result"]
        states = [item["state"] for item in results]
        if all(s in ("done", "failed") for s in states):
            break
        time.sleep(interval)

    for item in results:
        if item["state"] != "done":
            print(f"FAILED: {item.get('data_id')} — {item.get('err_msg')}")
            continue
        # Keep each PDF in its own directory so full.md, images/, and JSON
        # artifacts from different files never overwrite each other.
        item_dir = item.get("data_id") or Path(item["file_name"]).stem
        out = Path(output_dir) / item_dir
        out.mkdir(parents=True, exist_ok=True)
        zip_bytes = requests.get(item["full_zip_url"]).content
        zip_path = out / "result.zip"
        zip_path.write_bytes(zip_bytes)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(out)
        zip_path.unlink()
```

## Result States

| State | Meaning |
|-------|---------|
| `pending` | Queued, not yet started |
| `running` | Extraction in progress |
| `done` | Complete; `full_zip_url` is available |
| `failed` | Error; check `err_msg` field |

## Batch Processing (multiple PDFs)

Send all files in one `file-urls/batch` request. The API returns one `signed_url` per file and one shared `batch_id`. Upload files concurrently, then poll the single `batch_id`.

```python
from concurrent.futures import ThreadPoolExecutor

pdf_paths = list(Path("papers/").glob("*.pdf"))

files_meta = [
    {"name": p.name, "is_ocr": False, "data_id": p.stem}
    for p in pdf_paths
]
r = requests.post("https://mineru.net/api/v4/file-urls/batch",
                  headers=HEADERS, json={"files": files_meta})
batch_id  = r.json()["data"]["batch_id"]
signed_urls = r.json()["data"]["file_urls"]   # same order as files_meta

def upload(pdf_path, signed_url):
    with open(pdf_path, "rb") as f:
        requests.put(signed_url, data=f).raise_for_status()

with ThreadPoolExecutor(max_workers=5) as ex:
    list(ex.map(upload, pdf_paths, signed_urls))

# poll once for the whole batch
poll_and_save(batch_id, output_dir="output/")
```

Each finished PDF is saved into its own subdirectory such as
`output/paper_a/full.md` and `output/paper_b/full.md`.

## Output Structure

For a single PDF, the downloaded ZIP expands to:
```
output/
  <uuid>_origin.pdf          # original PDF copy
  full.md                    # full Markdown (preferred output)
  layout.json                # page layout structure
  <uuid>_content_list.json   # structured content list
  images/                    # extracted figures and tables
```

For a batch job, each PDF gets its own folder:
```
output/
  paper_a/
    full.md
    images/
    ...
  paper_b/
    full.md
    images/
    ...
```

Read `full.md` as the primary extraction result.

## Common Failures

| Error | Cause | Fix |
|-------|-------|-----|
| 403 on OSS upload | `Content-Type` header set | Remove Content-Type from PUT request |
| `type mismatch for field "files"` | Wrong request body shape | Use `{"files": [...]}` not `{"batch_id": ..., "files": [...]}` |
| `failed to read file` | Unsigned/wrong URL | Use the exact `signed_url` from step 1 |
| Token missing / 401 | `MINERU_TOKEN` not set | `export MINERU_TOKEN=...` |
| State stuck at `pending` | Server queue | Increase poll interval, wait longer |
