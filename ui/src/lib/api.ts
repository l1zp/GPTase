const API_PREFIX = '/api';
const WS_PREFIX = '/ws';

function normalizePath(path: string, prefix: string) {
  if (path.startsWith(prefix)) {
    return path;
  }
  return `${prefix}${path.startsWith('/') ? path : `/${path}`}`;
}

export function apiPath(path: string) {
  return normalizePath(path, API_PREFIX);
}

export async function apiFetch(path: string, init?: RequestInit) {
  return fetch(apiPath(path), init);
}

export async function apiGetJson<T>(path: string) {
  const response = await apiFetch(path);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export function createAppWebSocket(path: string) {
  const normalizedPath = normalizePath(path, WS_PREFIX);
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return new WebSocket(`${protocol}//${window.location.host}${normalizedPath}`);
}

export function workspaceFileUrl(path: string) {
  return `${apiPath('/workspace/file')}?path=${encodeURIComponent(path)}`;
}
