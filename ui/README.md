# GPTase UI

`ui/` is the standalone frontend app for GPTase. It stays in the same repository as the Python backend, but its development workflow is isolated.

## Development

Start the backend first:

```bash
gptase web --host 0.0.0.0 --port 8000
```

Then start the frontend dev server:

```bash
cd ui
npm install
npm run dev
```

Vite proxies browser requests for `/api/*` and `/ws/*` to `http://localhost:8000`, so the frontend always talks to the backend through the same app paths.

## Production

Build the frontend:

```bash
cd ui
npm run build
```

The output goes to `ui/dist`. In production mode, FastAPI serves the built SPA and static assets directly from that directory.

If `ui/dist` does not exist, `gptase web` still starts the API, but the UI will not be served.

## Contract Baseline

The frontend currently depends on these backend routes:

- `/api/agents`
- `/api/chat`
- `/api/sessions/*`
- `/api/memory/*`
- `/api/evals*`
- `/api/workspace/*`
- `/ws/plan/{session_id}`

When changing backend responses for these routes, update the frontend types in `ui/src/types.ts` and verify the UI with a local build.

## Plan Workspace Explorer

The dedicated extraction workspace page lives at `/workspace/plan-explorer`.

Current local dev assumptions:

- Vite proxies `/api/*` and `/ws/*` to `http://localhost:8765`
- The current default workspace root in the page is `/Users/ryanxu/CodeBase/GPTase`

Current layout policy:

- Base rule: tasks with `extraction_items` render as `left evidence + right results`
- `enzyme-kinetics-extractor`: specialized renderer
  - left side shows only source-text evidence
  - right side prefers task CSV rows and renders a structured kinetics table
  - source images are intentionally hidden because anchors often land on multi-panel captions
- `vision-image-analyzer`: specialized renderer
  - source image resolution prefers `payload.image_number` mapped against markdown image order
  - right side renders per-image text/table results

These renderers are schema-specific to the current agent outputs, but they are not hardcoded to one specific run directory.

Current comparison baseline:

- Page params:
  - `workspace_root=/Users/ryanxu/CodeBase/feat_web`
  - `document_name=listov2025`
  - `plan_id=enzyme_extraction_pipeline`
  - `run_id=enzyme_extraction_pipeline_20260326_184929`
- Saved API snapshot:
  - [`docs/snapshots/plan-workspace/listov2025_enzyme_extraction_pipeline_20260326_184929.api.json`](/Users/ryanxu/CodeBase/feat_web/docs/snapshots/plan-workspace/listov2025_enzyme_extraction_pipeline_20260326_184929.api.json)
- Saved page screenshot:
  - [`docs/snapshots/plan-workspace/listov2025_enzyme_extraction_pipeline_20260326_184929.page.png`](/Users/ryanxu/CodeBase/feat_web/docs/snapshots/plan-workspace/listov2025_enzyme_extraction_pipeline_20260326_184929.page.png)
