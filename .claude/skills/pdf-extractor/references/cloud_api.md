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

def poll_and_save(batch_id, output_dir, interval=5):
    # MinerU server-side concurrency is generous — a 30-file batch typically
    # completes in 40-90s wall-clock. Polling every 5s is a good tradeoff;
    # 10s wastes a noticeable share of total time waiting for the next tick.
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

### Small batch (≤ 30 files, simple case)

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

def upload(pdf_path, signed_url, attempts=3):
    # The OSS edge will occasionally close the connection mid-PUT on
    # large payloads (>50 MB cumulative across concurrent workers).
    # Retry with backoff before giving up so transient resets don't
    # kill the whole batch.
    import time
    for i in range(attempts):
        try:
            with open(pdf_path, "rb") as f:
                requests.put(signed_url, data=f, timeout=600).raise_for_status()
            return
        except Exception:
            if i == attempts - 1:
                raise
            time.sleep(3 * (i + 1))

with ThreadPoolExecutor(max_workers=3) as ex:
    # 3 workers is the sweet spot — 5+ workers caused RemoteDisconnected
    # on the OSS edge during real 30-file batches. The bottleneck is the
    # network, not the API.
    list(ex.map(upload, pdf_paths, signed_urls))

poll_and_save(batch_id, output_dir="output/")
```

Each finished PDF is saved into its own subdirectory such as `output/paper_a/full.md`.

### Large batch (chunking when N > batch limit)

For real corpora (50+ PDFs), split into chunks of ~30 and isolate each
chunk's errors. The reason for per-chunk `try/except` is concrete: a
single network blip during upload taints that batch's `batch_id` (the
server has signed URLs it never received content for), and without
isolation one bad batch kills every later batch too.

```python
import time, io, zipfile
from concurrent.futures import ThreadPoolExecutor

CHUNK_SIZE = 30

# Each job knows where its result should land — not necessarily
# `output_dir/{data_id}/`. This decoupling lets you place each PDF's
# output into any directory (e.g. `markdowns/paperA/main/` vs
# `markdowns/paperA/SI/SI_X/`) by looking up by data_id at result time.
jobs = []  # list of (pdf_path, target_dir, data_id)
for paper_dir in Path("papers/").iterdir():
    for pdf in paper_dir.glob("*.pdf"):
        target = Path("output") / paper_dir.name / pdf.stem
        # Idempotent skip: a directory containing full.md is treated
        # as already extracted. Re-running the whole script is safe.
        if (target / "full.md").exists():
            continue
        data_id = f"{paper_dir.name}__{pdf.stem}"
        jobs.append((pdf, target, data_id))

job_map = {did: (pdf, tgt) for pdf, tgt, did in jobs}

for chunk_start in range(0, len(jobs), CHUNK_SIZE):
    chunk = jobs[chunk_start:chunk_start + CHUNK_SIZE]
    try:
        # 1) request URLs
        files_meta = [{"name": p.name, "is_ocr": False, "data_id": did}
                      for p, _, did in chunk]
        r = requests.post(BATCH_API, headers=HEADERS,
                          json={"files": files_meta}, timeout=60)
        r.raise_for_status()
        batch_id    = r.json()["data"]["batch_id"]
        signed_urls = r.json()["data"]["file_urls"]

        # 2) upload (each PUT retries on its own — see small-batch example)
        pairs = list(zip([p for p, _, _ in chunk], signed_urls))
        with ThreadPoolExecutor(max_workers=3) as ex:
            list(ex.map(lambda pair: upload(*pair), pairs))

        # 3) poll
        results = poll_only(batch_id, expected=len(chunk))

        # 4) save each result into its precomputed target dir
        for item in results:
            if item["state"] != "done":
                print(f"FAIL {item.get('data_id')}: {item.get('err_msg')}")
                continue
            _, target = job_map[item["data_id"]]
            target.mkdir(parents=True, exist_ok=True)
            zb = requests.get(item["full_zip_url"], timeout=600).content
            with zipfile.ZipFile(io.BytesIO(zb)) as z:
                z.extractall(target)
    except Exception as e:
        # The whole chunk is lost on this attempt, but subsequent chunks
        # still get their turn. Re-running the script picks this up via
        # the idempotent skip.
        print(f"chunk {chunk_start//CHUNK_SIZE}: {type(e).__name__}: {e}")
        continue
```

`poll_only` is a thin variant of `poll_and_save` that just returns the
results list without doing the save step (because the save logic now
needs to look up targets from `job_map`):

```python
def poll_only(batch_id, expected, interval=5):
    url = f"https://mineru.net/api/v4/extract-results/batch/{batch_id}"
    while True:
        r = requests.get(url, headers=HEADERS, timeout=60)
        results = r.json()["data"]["extract_result"]
        running = sum(1 for it in results if it["state"] in ("pending", "running"))
        if running == 0:
            return results
        time.sleep(interval)
```

### Key patterns this enables

1. **Idempotent re-runs**: marker file (`full.md` / `main.md`) under `target/` ⇒ skip. Long jobs that crash partway can be resumed by just re-running.
2. **Arbitrary output layout**: `data_id` is your only handle for mapping results to specific target dirs. Encode the routing info (e.g. `paper__section`) in the data_id so the lookup is unambiguous.
3. **Error containment**: every chunk is independent; one chunk's bad luck doesn't take the rest down.

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

## When to set `is_ocr: true`

Default `is_ocr: false` works for ~95% of academic PDFs — modern publishers
embed a real text layer that MinerU parses directly. Flip to `true` only for
genuinely scanned documents (old conference proceedings, photocopied pre-2000
papers, manuscripts where every page is essentially an image).

Cheap detection heuristic before submitting:

```python
import fitz  # pip install pymupdf
chars_per_page = sum(len(p.get_text()) for p in fitz.open(pdf_path)) / max(1, fitz.open(pdf_path).page_count)
is_ocr = chars_per_page < 100   # heuristic; native-text PDFs are 1000+
```

The penalty for getting this wrong is asymmetric: OCRing a native-text PDF
adds processing time but recovers fine; *failing* to OCR a true scan leaves
`full.md` essentially empty. When in doubt, set `true`.

## Skipping non-PDF inputs

MinerU only accepts PDF. If a corpus contains `.zip`, `.xlsx`, `.docx`
supplementary files (common with Nature/Wiley SIs), filter them out before
enumerating jobs:

```python
jobs = [p for p in paper_dir.glob("*") if p.suffix.lower() == ".pdf"]
```

Submitting a non-PDF returns a per-file `failed` state with `err_msg`
mentioning content-type, not a hard batch error — but it still costs a
batch slot and a poll cycle, so filter upfront.

## Common Failures

| Error | Cause | Fix |
|-------|-------|-----|
| 403 on OSS upload | `Content-Type` header set | Remove Content-Type from PUT request |
| `RemoteDisconnected('Remote end closed connection without response')` mid-PUT | OSS edge closing connection under concurrent large-payload uploads | Drop `max_workers` from 5 to 3; add per-file retry (3 attempts, 3s/6s/9s backoff) — see the small-batch example above |
| `type mismatch for field "files"` | Wrong request body shape | Use `{"files": [...]}` not `{"batch_id": ..., "files": [...]}` |
| `failed to read file` | Unsigned/wrong URL | Use the exact `signed_url` from step 1 |
| Token missing / 401 | `MINERU_TOKEN` not set | `export MINERU_TOKEN=...` |
| State stuck at `pending` | Server queue | Increase poll interval, wait longer |
| One bad chunk kills later chunks | Single `try/except` wrapping the whole multi-chunk loop | Per-chunk `try/except` so error in chunk N doesn't skip chunks N+1, N+2, … — see large-batch example above |
