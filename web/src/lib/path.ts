// Mirrors server/verify/checker.py resolve_path + _normalize_path, so the
// source drawer shows exactly the raw value the verifier checked.

const TOKEN = /([^.[\]]+)|\[(\d+)\]/g;

export function normalizePath(toolName: string, path: string): string {
  const prefix = `${toolName}_response.`;
  return path.startsWith(prefix) ? path.slice(prefix.length) : path;
}

export function resolvePath(entry: unknown, path: string): unknown {
  let current: unknown = entry;
  for (const match of path.matchAll(TOKEN)) {
    const [, key, idx] = match;
    if (current == null || typeof current !== "object") return undefined;
    current = key !== undefined ? (current as Record<string, unknown>)[key] : (current as unknown[])[Number(idx)];
  }
  return current;
}
