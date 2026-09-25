import { type KeyboardEvent, useEffect, useRef } from "react";
import { type Lang, wardName } from "../lib/prefs";
import styles from "./RankedList.module.css";

export interface RankedRow {
  ward_key: string;
  ward_name: string;
  ward_name_kn: string;
  corporation: string;
  value: number;
}

interface Props {
  rows: RankedRow[];
  format: (v: number) => string;
  lang: Lang;
  selectedKey: string | null;
  onSelect: (key: string) => void;
  /** Bar length reflects the value relative to the list's range. */
  barFromMin?: boolean;
  diverging?: boolean;
}

export function RankedList({ rows, format, lang, selectedKey, onSelect, barFromMin = true, diverging = false }: Props) {
  const listRef = useRef<HTMLOListElement>(null);
  const values = rows.map((r) => r.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const absMax = Math.max(...values.map(Math.abs), 1e-9);

  useEffect(() => {
    if (!selectedKey) return;
    const el = listRef.current?.querySelector<HTMLElement>(`[data-key="${CSS.escape(selectedKey)}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [selectedKey]);

  const onKeyDown = (e: KeyboardEvent<HTMLOListElement>) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp" && e.key !== "Home" && e.key !== "End") return;
    const buttons = [...(listRef.current?.querySelectorAll<HTMLButtonElement>("button[data-key]") ?? [])];
    const i = buttons.indexOf(document.activeElement as HTMLButtonElement);
    let next = i;
    if (e.key === "ArrowDown") next = Math.min(buttons.length - 1, i + 1);
    if (e.key === "ArrowUp") next = Math.max(0, i - 1);
    if (e.key === "Home") next = 0;
    if (e.key === "End") next = buttons.length - 1;
    if (next !== i && buttons[next]) {
      e.preventDefault();
      buttons[next].focus();
    }
  };

  return (
    <ol className={styles.list} ref={listRef} onKeyDown={onKeyDown}>
      {rows.map((r, i) => {
        const width = diverging
          ? (Math.abs(r.value) / absMax) * 50
          : barFromMin
            ? max === min
              ? 100
              : 8 + ((r.value - min) / (max - min)) * 92
            : (r.value / max) * 100;
        return (
          <li key={r.ward_key}>
            <button
              type="button"
              data-key={r.ward_key}
              className={`${styles.row} ${selectedKey === r.ward_key ? styles.selected : ""}`}
              onClick={() => onSelect(r.ward_key)}
              aria-current={selectedKey === r.ward_key ? "true" : undefined}
            >
              <span className={styles.rank}>{i + 1}</span>
              <span className={styles.name}>
                <span className={lang === "kn" ? "kn" : ""}>{wardName(r, lang)}</span>
                <span className={styles.corp}>{r.corporation}</span>
              </span>
              <span className={styles.metric}>
                <span className={styles.value}>{format(r.value)}</span>
                <span className={`${styles.track} ${diverging ? styles.trackDiv : ""}`} aria-hidden="true">
                  <span
                    className={`${styles.bar} ${diverging && r.value < 0 ? styles.cool : ""}`}
                    style={
                      diverging
                        ? { width: `${width}%`, [r.value < 0 ? "right" : "left"]: "50%" }
                        : { width: `${width}%` }
                    }
                  />
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
