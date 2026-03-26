import { FolderSearch, RefreshCw } from 'lucide-react';
import { FormEvent, useEffect, useMemo, useState } from 'react';

import { apiFetch, workspaceFileUrl } from '../lib/api';
import type {
  ApiWorkspaceCsvFile,
  ApiWorkspaceDocument,
  ApiWorkspacePlan,
  ApiWorkspaceRunSummary,
  ApiWorkspaceTaskSummary,
} from '../types';

const DEFAULT_WORKSPACE_ROOT = '/Users/ryanxu/CodeBase/GPTase';
const DEFAULT_DOCUMENT_NAME = 'listov2025';
const DEFAULT_PLAN_ID = 'enzyme_extraction_pipeline';


export function PlanWorkspaceExplorer() {
  const params = useMemo(() => new URLSearchParams(window.location.search), []);
  const [workspaceRoot, setWorkspaceRoot] = useState(params.get('workspace_root') ?? DEFAULT_WORKSPACE_ROOT);
  const [documentName, setDocumentName] = useState(params.get('document_name') ?? DEFAULT_DOCUMENT_NAME);
  const [planId, setPlanId] = useState(params.get('plan_id') ?? DEFAULT_PLAN_ID);
  const [workspace, setWorkspace] = useState<ApiWorkspaceDocument | null>(null);
  const [markdownImagePaths, setMarkdownImagePaths] = useState<string[]>([]);
  const [availablePlans, setAvailablePlans] = useState<ApiWorkspacePlan[]>([]);
  const [selectedRunId, setSelectedRunId] = useState(params.get('run_id'));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadPlans();
  }, []);

  useEffect(() => {
    void loadWorkspace(selectedRunId);
  }, [workspaceRoot, documentName, planId, selectedRunId]);

  useEffect(() => {
    if (!workspace?.markdown_path) {
      setMarkdownImagePaths([]);
      return;
    }

    void apiFetch(`/workspace/file?path=${encodeURIComponent(workspace.markdown_path)}`)
      .then((response) => response.text())
      .then((text) => {
        const matches = Array.from(text.matchAll(/!\[.*?\]\(([^)]+)\)/g));
        setMarkdownImagePaths(matches.map((match) => match[1]));
      })
      .catch(() => setMarkdownImagePaths([]));
  }, [workspace?.markdown_path]);

  const selectedRun = useMemo<ApiWorkspaceRunSummary | null>(() => {
    if (!workspace) {
      return null;
    }
    return (
      workspace.runs.find((run) => run.run_id === (selectedRunId ?? workspace.selected_run_id ?? '')) ??
      workspace.runs[0] ??
      null
    );
  }, [workspace, selectedRunId]);

  const visibleTasks = useMemo(() => {
    if (!selectedRun) {
      return [];
    }
    return selectedRun.tasks.filter((task) => {
      const replicaMatch = task.task_id.match(/_r(\d+)$/);
      if (!replicaMatch) {
        return true;
      }
      return replicaMatch[1] === '1';
    });
  }, [selectedRun]);

  // Tasks that have CSV results or at least one extraction item with actual data
  const tasksWithData = useMemo(
    () =>
      visibleTasks.filter(
        (task) =>
          task.csv_files.length > 0 ||
          task.extraction_items.some((item) => {
            const values = Object.values(item.payload);
            return values.length > 0 && values.some((v) => v !== null && v !== undefined && v !== '');
          }),
      ),
    [visibleTasks],
  );

  // Representative anchor line per task: minimum anchor line across all items
  const taskAnchorLine = useMemo<Record<string, number>>(
    () =>
      Object.fromEntries(
        tasksWithData.map((task) => {
          const lines = task.extraction_items.flatMap((item) =>
            item.anchors.map((a) => a.line_number),
          );
          return [task.task_id, lines.length > 0 ? Math.min(...lines) : 0];
        }),
      ),
    [tasksWithData],
  );

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSelectedRunId(null);
    const nextParams = new URLSearchParams();
    nextParams.set('workspace_root', workspaceRoot);
    nextParams.set('document_name', documentName);
    nextParams.set('plan_id', planId);
    window.history.replaceState({}, '', `${window.location.pathname}?${nextParams.toString()}`);
    void loadWorkspace(null);
  };

  const loadPlans = async () => {
    try {
      const response = await apiFetch('/workspace/plans');
      if (!response.ok) {
        return;
      }
      const data = (await response.json()) as ApiWorkspacePlan[];
      setAvailablePlans(data);
    } catch {
      // Keep defaults.
    }
  };

  const loadWorkspace = async (requestedRunId?: string | null) => {
    setLoading(true);
    setError(null);
    try {
      const query = new URLSearchParams({
        workspace_root: workspaceRoot,
        document_name: documentName,
        plan_id: planId,
      });
      if (requestedRunId) {
        query.set('run_id', requestedRunId);
      }
      const response = await apiFetch(`/workspace/document?${query.toString()}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = (await response.json()) as ApiWorkspaceDocument;
      setWorkspace(data);
      setSelectedRunId((prev) => prev ?? data.selected_run_id ?? data.runs[0]?.run_id ?? null);
    } catch (loadError) {
      setWorkspace(null);
      setError(loadError instanceof Error ? loadError.message : '加载失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="plan-workspace-shell">
      <header className="plan-workspace-header">
        <div>
          <div className="plan-workspace-kicker">Plan Workspace</div>
          <h1>第二步抽取工作台</h1>
          <p>每条结果对应原文证据，卡片形式展示。</p>
        </div>
        <div className="plan-workspace-actions">
          <a className="secondary-button" href="/">
            返回会话 UI
          </a>
          <button className="secondary-button" onClick={() => void loadWorkspace(selectedRunId)} disabled={loading}>
            <RefreshCw size={16} />
            刷新
          </button>
        </div>
      </header>

      <form className="workspace-query-bar" onSubmit={handleSubmit}>
        <label>
          <span>Plan</span>
          <select value={planId} onChange={(event) => setPlanId(event.target.value)}>
            {availablePlans.length > 0 ? (
              availablePlans.map((plan) => (
                <option key={plan.plan_id} value={plan.plan_id}>
                  {plan.plan_id}
                </option>
              ))
            ) : (
              <option value={planId}>{planId}</option>
            )}
          </select>
        </label>
        <label>
          <span>Document</span>
          <input value={documentName} onChange={(event) => setDocumentName(event.target.value)} />
        </label>
        <label className="is-wide">
          <span>Workspace Root</span>
          <input
            value={workspaceRoot}
            onChange={(event) => setWorkspaceRoot(event.target.value)}
            placeholder="留空时使用服务当前工作目录"
          />
        </label>
        <button className="primary-button" type="submit" disabled={loading}>
          <FolderSearch size={16} />
          加载工作台
        </button>
      </form>

      <section className="workspace-meta-bar workspace-meta-bar-3col">
        <div className="workspace-meta-card">
          <span>当前运行</span>
          <strong>{selectedRun?.run_id ?? '暂无'}</strong>
        </div>
        <div className="workspace-meta-card">
          <span>抽取任务</span>
          <strong>{tasksWithData.length} 个</strong>
        </div>
        <div className="workspace-run-switch">
          <span>切换运行</span>
          <select
            value={selectedRun?.run_id ?? ''}
            onChange={(event) => setSelectedRunId(event.target.value)}
            disabled={!workspace || workspace.runs.length === 0}
          >
            {(workspace?.runs ?? []).map((run) => (
              <option key={run.run_id} value={run.run_id}>
                {run.run_id}
              </option>
            ))}
          </select>
        </div>
      </section>

      {error ? <div className="workspace-error-banner">加载失败：{error}</div> : null}

      <main className="task-card-list">
        {loading ? (
          <div className="workspace-empty-panel">
            <p>加载中...</p>
          </div>
        ) : tasksWithData.length === 0 ? (
          <div className="workspace-empty-panel">
            <p>当前运行没有第二步结果可展示。</p>
          </div>
        ) : (
          tasksWithData.map((task) => (
            <TaskCard
              key={`${selectedRun?.run_id ?? 'default'}:${task.task_id}`}
              task={task}
              anchorLine={taskAnchorLine[task.task_id] ?? 0}
              documentDir={workspace?.document_dir ?? ''}
              markdownImagePaths={markdownImagePaths}
            />
          ))
        )}
      </main>
    </div>
  );
}

interface TaskCardProps {
  task: ApiWorkspaceTaskSummary;
  anchorLine: number;
  documentDir: string;
  markdownImagePaths: string[];
}

/** Extract first image path from markdown excerpt, e.g. "![](images/foo.jpg)" → "images/foo.jpg" */
function extractImagePath(text: string): string | null {
  const match = text.match(/!\[.*?\]\(([^)]+)\)/);
  return match ? match[1] : null;
}

/** Parse a raw CSV string into columns + rows (handles simple non-quoted CSVs). */
function parseCsvString(raw: string): { columns: string[]; rows: Record<string, string>[] } {
  const lines = raw.trim().split('\n');
  if (lines.length === 0) return { columns: [], rows: [] };
  const columns = lines[0].split(',');
  const rows = lines.slice(1).map((line) => {
    const vals = line.split(',');
    return Object.fromEntries(columns.map((col, i) => [col, vals[i] ?? '']));
  });
  return { columns, rows };
}

function tryParseJsonText(value: string) {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function formatFieldLabel(key: string) {
  return key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\bkm\b/gi, 'Km')
    .replace(/\bkcat km\b/gi, 'kcat/Km')
    .replace(/\bpdb ids\b/gi, 'PDB IDs');
}

function formatFieldValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '未提供';
  }
  if (Array.isArray(value)) {
    return value.length > 0 ? value.map((item) => formatFieldValue(item)).join(', ') : '无';
  }
  if (typeof value === 'object') {
    return JSON.stringify(value, null, 2);
  }
  return String(value);
}

function extractAnchorImagePath(item: ApiWorkspaceTaskSummary['extraction_items'][number]) {
  const anchorText = item.anchors[0]?.excerpt || item.anchors[0]?.snippet || '';
  return extractImagePath(anchorText);
}

function normalizeEvidenceRecord(payload: Record<string, unknown>) {
  const normalized: Record<string, unknown> = {};
  for (const [key, rawValue] of Object.entries(payload)) {
    const value =
      typeof rawValue === 'string' && (rawValue.startsWith('{') || rawValue.startsWith('['))
        ? (tryParseJsonText(rawValue) ?? rawValue)
        : rawValue;

    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      for (const [subKey, subValue] of Object.entries(value as Record<string, unknown>)) {
        normalized[subKey] = subValue;
      }
      continue;
    }

    normalized[key] = value;
  }
  return normalized;
}

function EvidenceFields({ payload }: { payload: Record<string, unknown> }) {
  const normalizedPayload = normalizeEvidenceRecord(payload);
  return (
    <div className="evidence-fields">
      {Object.entries(normalizedPayload).map(([key, value]) => {
        const isNestedObject =
          typeof value === 'object' && value !== null && !Array.isArray(value);

        if (isNestedObject) {
          return (
            <div key={key} className="evidence-field">
              <div className="evidence-field-label">{formatFieldLabel(key)}</div>
              <div className="evidence-subfields">
                {Object.entries(value as Record<string, unknown>).map(([subKey, subValue]) => (
                  <div key={subKey} className="evidence-subfield">
                    <span>{formatFieldLabel(subKey)}</span>
                    <strong>{formatFieldValue(subValue)}</strong>
                  </div>
                ))}
              </div>
            </div>
          );
        }

        return (
          <div key={key} className="evidence-field">
            <div className="evidence-field-label">{formatFieldLabel(key)}</div>
            <div className="evidence-field-value">{formatFieldValue(value)}</div>
          </div>
        );
      })}
    </div>
  );
}

function formatCompactMetric(value: unknown, unit: unknown) {
  const base = value === null || value === undefined || value === '' ? '未提供' : String(value);
  const suffix = unit === null || unit === undefined || unit === '' ? '' : ` ${String(unit)}`;
  return `${base}${suffix}`;
}

function EvidenceResultsTable({ rows }: { rows: Record<string, unknown>[] }) {
  const columns = [
    { key: 'enzyme_name', label: 'Enzyme' },
    { key: 'substrates', label: 'Substrates' },
    { key: 'kcat', label: 'kcat' },
    { key: 'Km', label: 'Km' },
    { key: 'kcatKm', label: 'kcat/Km' },
    { key: 'Tm', label: 'Tm' },
    { key: 'mutations', label: 'Mutations' },
    { key: 'pdb_ids', label: 'PDB IDs' },
  ] as const;

  const tableRows = rows.map((row) => ({
    enzyme_name: formatFieldValue(row.enzyme_name),
    substrates: formatFieldValue(row.substrates),
    kcat: formatCompactMetric(row.kcat, row.kcat_unit),
    Km: formatCompactMetric(row.Km, row.Km_unit),
    kcatKm: formatCompactMetric(row.kcat_KM ?? row['kcat/KM'], row.kcat_KM_unit ?? row['kcat/KM_unit']),
    Tm: formatCompactMetric(row.Tm, row.Tm_unit),
    mutations: formatFieldValue(row.mutations),
    pdb_ids: formatFieldValue(row.pdb_ids),
  }));

  return (
    <div className="evidence-table-wrap">
      <table className="evidence-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key}>{column.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tableRows.map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column.key}>{row[column.key]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TaskCard({ task, anchorLine, documentDir, markdownImagePaths }: TaskCardProps) {
  const [csv, setCsv] = useState<ApiWorkspaceCsvFile | null>(null);

  useEffect(() => {
    if (!task.csv_files?.[0]) {
      setCsv(null);
      return;
    }
    void apiFetch(`/workspace/file?path=${encodeURIComponent(task.csv_files[0])}`)
      .then((r) => r.json() as Promise<ApiWorkspaceCsvFile>)
      .then((data) => setCsv(data))
      .catch(() => setCsv(null));
  }, [task.csv_files]);

  const isVisionTask =
    task.agent_name === 'vision-image-analyzer' && task.extraction_items.length > 0;
  const hasEvidenceItems = task.extraction_items.length > 0;
  const csvRowMap = useMemo(() => {
    if (!csv) return new Map<string, Record<string, string>>();
    const map = new Map<string, Record<string, string>>();
    for (const row of csv.rows) {
      const key = row['enzyme_name'] || row['figure_id'] || row['title'] || '';
      if (key) map.set(key, row);
    }
    return map;
  }, [csv]);
  const evidenceGroups = useMemo(() => {
    if (!hasEvidenceItems || isVisionTask) return null;

    type EvidenceItem = (typeof task.extraction_items)[number];
    type Group = {
      key: string;
      imagePath: string | null;
      anchor: EvidenceItem['anchors'][number] | null;
      items: EvidenceItem[];
    };

    const grouped = new Map<string, Group>();
    const ordered: Group[] = [];

    for (const item of task.extraction_items) {
      const imagePath = extractAnchorImagePath(item);
      const anchor = item.anchors[0] ?? null;
      const key = `${imagePath ?? 'no-image'}::${anchor?.excerpt ?? anchor?.snippet ?? item.title}`;
      let group = grouped.get(key);
      if (!group) {
        group = { key, imagePath, anchor, items: [] };
        grouped.set(key, group);
        ordered.push(group);
      }
      group.items.push(item);
    }

    return ordered;
  }, [hasEvidenceItems, isVisionTask, task.extraction_items]);

  /**
   * Vision layout: group items by their resolved physical image path.
   *
   * vision_table items have reliable anchor images.
   * vision_analysis items have no anchors; we resolve their image by matching
   * their title against vision_table titles (exact prefix, e.g.
   * "Figure 3a: bar chart" → "Figure 3a", or figure-number prefix "Figure 3c" → "Figure 3").
   */
  const visionGroups = useMemo(() => {
    if (!isVisionTask) return null;

    type VisionItem = (typeof task.extraction_items)[number];
    type Group = { imagePath: string | null; items: VisionItem[] };

    // Build: table_title → image_path from vision_table anchor excerpts
    const tableTitleToImage = new Map<string, string>();
    for (const item of task.extraction_items) {
      if (item.item_type === 'vision_table') {
        const anchorText = item.anchors[0]?.excerpt || item.anchors[0]?.snippet || '';
        const imgPath = extractImagePath(anchorText);
        if (imgPath) tableTitleToImage.set(item.title, imgPath);
      }
    }

    /** Resolve image path for any item (table or analysis). */
    const resolveImage = (item: VisionItem): string | null => {
      const imageNumber = item.payload?.image_number;
      if (
        typeof imageNumber === 'number' &&
        imageNumber > 0 &&
        imageNumber <= markdownImagePaths.length
      ) {
        return markdownImagePaths[imageNumber - 1];
      }

      // 1. Direct anchor image
      const anchorText = item.anchors[0]?.excerpt || item.anchors[0]?.snippet || '';
      const direct = extractImagePath(anchorText);
      if (direct) return direct;

      // 2. Exact table-title prefix: "Figure 3a: ..." → "Figure 3a"
      for (const [tableTitle, imgPath] of tableTitleToImage) {
        if (item.title.startsWith(tableTitle + ':') || item.title.startsWith(tableTitle + ' ')) {
          return imgPath;
        }
      }

      // 3. Figure-number prefix: "Figure 3c" → first table title starting with "Figure 3"
      const figNumMatch = item.title.match(/^(Figure\s+\d+)/i);
      if (figNumMatch) {
        const prefix = figNumMatch[1].toLowerCase();
        for (const [tableTitle, imgPath] of tableTitleToImage) {
          if (tableTitle.toLowerCase().startsWith(prefix)) return imgPath;
        }
      }

      return null;
    };

    // Group by resolved image path (preserve first-seen order)
    const groupMap = new Map<string, Group>();
    const ordered: Group[] = [];
    const NO_IMG_KEY = '__no_image__';

    for (const item of task.extraction_items) {
      const imgPath = resolveImage(item);
      const key = imgPath ?? NO_IMG_KEY;
      let group = groupMap.get(key);
      if (!group) {
        group = { imagePath: imgPath, items: [] };
        groupMap.set(key, group);
        ordered.push(group);
      }
      group.items.push(item);
    }
    return ordered;
  }, [task, isVisionTask, markdownImagePaths]);

  return (
    <div className="task-card">
      <div className="task-card-header">
        <div>
          <div className="result-task-kicker">{task.agent_name}</div>
          <div className="result-task-title">{task.task_id}</div>
        </div>
        <div className="result-task-meta">{anchorLine ? `原文第 ${anchorLine} 行` : '无锚点'}</div>
      </div>

      {isVisionTask && visionGroups ? (
        // Vision layout: one section per source image
        <div className="vision-groups">
          {visionGroups.map((group, gi) => (
            <div key={gi} className="vision-group">
              {group.imagePath ? (
                <img
                  className="task-card-source-image"
                  src={workspaceFileUrl(`${documentDir}/${group.imagePath}`)}
                  alt=""
                />
              ) : null}
              <div className="vision-items">
                {group.items.map((item) => {
                  const payload = item.payload as Record<string, unknown>;
                  return (
                    <div key={item.item_id} className="vision-item">
                      <div className="vision-item-title">{item.title}</div>
                      {item.item_type === 'vision_table' && typeof payload['csv_data'] === 'string' ? (
                        <VisionTable csvData={payload['csv_data'] as string} />
                      ) : typeof payload['content'] === 'string' ? (
                        <p className="vision-item-content">{payload['content'] as string}</p>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      ) : hasEvidenceItems && evidenceGroups ? (
        <div className="evidence-card-list">
          {evidenceGroups.map((group) => {
            const tableRows = group.items.map((item) => {
              const payload = item.payload as Record<string, unknown>;
              const csvRow = csvRowMap.get(item.title);
              const displayPayload = csvRow
                ? Object.fromEntries(
                    Object.entries(csvRow).map(([key, value]) => [
                      key,
                      typeof value === 'string' && (value.startsWith('{') || value.startsWith('['))
                        ? (tryParseJsonText(value) ?? value)
                        : value,
                    ]),
                  )
                : payload;
              return normalizeEvidenceRecord(displayPayload);
            });

            return (
              <div key={group.key} className="evidence-card evidence-card-split">
                <aside className="evidence-card-source">
                  {task.agent_name !== 'enzyme-kinetics-extractor' && group.imagePath ? (
                    <img
                      className="task-card-source-image"
                      src={workspaceFileUrl(`${documentDir}/${group.imagePath}`)}
                      alt=""
                    />
                  ) : null}
                  <div className="evidence-anchor">
                    <div className="evidence-anchor-label">原文证据</div>
                    <pre>{group.anchor?.excerpt || group.anchor?.snippet || '没有可用锚点'}</pre>
                  </div>
                </aside>

                <div className="evidence-card-main">
                  {tableRows.length > 0 ? <EvidenceResultsTable rows={tableRows} /> : null}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        // Standard layout: optional source context + full CSV table
        <>
          <div className="task-card-results">
            <div className="summary-card-label">提取结果</div>
            {csv ? (
              <div className="csv-preview">
                <table>
                  <thead>
                    <tr>
                      {csv.columns.map((col) => (
                        <th key={col}>{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {csv.rows.map((row, index) => (
                      <tr key={index}>
                        {csv.columns.map((col) => (
                          <td key={col}>{row[col]}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <pre>
                {JSON.stringify(
                  task.summary ?? task.extraction_items.map((i) => i.payload),
                  null,
                  2,
                )}
              </pre>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function VisionTable({ csvData }: { csvData: string }) {
  const { columns, rows } = useMemo(() => parseCsvString(csvData), [csvData]);
  if (columns.length === 0) return null;
  return (
    <div className="csv-preview">
      <table>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map((col) => (
                <td key={col}>{row[col]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
