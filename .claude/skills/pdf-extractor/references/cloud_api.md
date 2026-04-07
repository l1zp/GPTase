# MinerU Cloud API Reference

Use this file when extracting via the MinerU cloud Precision API.

## When To Use

Prefer cloud API over local CLI whenever `MINERU_TOKEN` is set. Advantages:
- No local model downloads or GPU required
- No Apple Silicon / transformers compatibility issues
- Supports true batch processing in a single request
- Higher and more consistent extraction quality

## Authentication

Token is stored in `.env` at the project root:

```
MINERU_TOKEN=eyJ0eXBlIjoiSldUIi...
```

Load it before running any extraction script:

```python
from dotenv import load_dotenv
import os

load_dotenv()   # reads .env from cwd or parent directories
TOKEN = os.environ["MINERU_TOKEN"]
```

Or in shell:

```bash
export $(grep MINERU_TOKEN .env | xargs)
```

Check: `echo $MINERU_TOKEN` should print a non-empty JWT.

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
        out = Path(output_dir)
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

## Output Structure

The downloaded ZIP expands to:
```
output/
  <uuid>_origin.pdf          # original PDF copy
  full.md                    # full Markdown (preferred output)
  layout.json                # page layout structure
  <uuid>_content_list.json   # structured content list
  images/                    # extracted figures and tables
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
