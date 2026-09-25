import { useQuery } from "@tanstack/react-query";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "../lib/api";
import { dateTime } from "../lib/format";
import { normalizePath, resolvePath } from "../lib/path";
import styles from "./SourceDrawer.module.css";

export interface SourceRef {
  toolResultId: string;
  path: string;
  /** What the chip showed, e.g. "40.5 °C". */
  shown: string;
  /** What the figure is, e.g. "2025 surface temperature, Padarayanapura". */
  label?: string;
}

interface Ctx {
  open: (ref: SourceRef, trigger: HTMLElement | null) => void;
  current: SourceRef | null;
}

const DrawerContext = createContext<Ctx | null>(null);

export function useSourceDrawer(): Ctx {
  const ctx = useContext(DrawerContext);
  if (!ctx) throw new Error("useSourceDrawer outside provider");
  return ctx;
}

export function SourceDrawerProvider({ children }: { children: ReactNode }) {
  const [current, setCurrent] = useState<SourceRef | null>(null);
  const triggerRef = useRef<HTMLElement | null>(null);

  const open = useCallback((ref: SourceRef, trigger: HTMLElement | null) => {
    triggerRef.current = trigger;
    setCurrent(ref);
  }, []);

  const close = useCallback(() => {
    setCurrent(null);
    triggerRef.current?.focus();
  }, []);

  const value = useMemo(() => ({ open, current }), [open, current]);
  return (
    <DrawerContext.Provider value={value}>
      {children}
      {current && <Drawer key={`${current.toolResultId}:${current.path}`} source={current} onClose={close} />}
    </DrawerContext.Provider>
  );
}

function Drawer({ source, onClose }: { source: SourceRef; onClose: () => void }) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const q = useQuery({
    queryKey: ["source", source.toolResultId],
    queryFn: () => api.source(source.toolResultId),
    // The audit row is written to BigQuery asynchronously right after the
    // tool runs, so a very fast click can arrive first. Retry briefly.
    retry: (count, err) => err instanceof ApiError && err.status === 404 && count < 4,
    retryDelay: 1500,
    staleTime: Infinity,
  });

  useEffect(() => {
    headingRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const raw = q.data ? resolvePath(q.data, normalizePath(q.data.tool_name, source.path)) : undefined;

  return (
    <aside className={styles.drawer} role="dialog" aria-modal="false" aria-labelledby="source-heading">
      <header className={styles.head}>
        <div>
          <h2 id="source-heading" ref={headingRef} tabIndex={-1} className={styles.title}>
            Source for <span className={styles.shown}>{source.shown}</span>
          </h2>
          {source.label && <p className={styles.label}>{source.label}</p>}
        </div>
        <button type="button" className={styles.close} onClick={onClose} aria-label="Close source">
          <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M3.5 3.5l9 9m0-9l-9 9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
        </button>
      </header>

      {q.isPending && <p className={styles.muted}>Looking up where this figure came from.</p>}
      {q.isError && (
        <p className={styles.muted}>
          {q.error instanceof ApiError && q.error.status === 404
            ? "This record is still being saved to the audit table. Close this and open the source again in a few seconds."
            : q.error.message}
        </p>
      )}
      {q.data && (
        <>
          <p className={styles.description}>{q.data.description}.</p>
          <dl className={styles.facts}>
            <div>
              <dt>Raw value</dt>
              <dd className={styles.value}>{formatRaw(raw)}</dd>
            </div>
            <div>
              <dt>Field</dt>
              <dd className={styles.value}>{normalizePath(q.data.tool_name, source.path)}</dd>
            </div>
            <div>
              <dt>Tool</dt>
              <dd className={styles.value}>{q.data.tool_name}</dd>
            </div>
            <div>
              <dt>Computed</dt>
              <dd>{dateTime(q.data.created_at)}</dd>
            </div>
          </dl>
          <details className={styles.params}>
            <summary>Parameters</summary>
            <dl>
              {Object.entries(q.data.params).map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd className={styles.value}>{v === null ? "none" : typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>
                </div>
              ))}
            </dl>
          </details>
          <p className={styles.id}>Record {source.toolResultId}</p>
        </>
      )}
    </aside>
  );
}

function formatRaw(v: unknown): string {
  if (v === undefined) return "Not found at this field";
  if (typeof v === "number") return String(v);
  if (typeof v === "string") return v;
  return JSON.stringify(v);
}
