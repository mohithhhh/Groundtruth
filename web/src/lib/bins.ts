// Map classification. Quantile bins by default (stated in the legend);
// change-over-time uses fixed symmetric breaks so zero is always the centre.

export type BinMethod = "quantile" | "fixed";

export interface Classification {
  method: BinMethod;
  /** Upper edge of each class except the last; length = classes - 1. */
  breaks: number[];
  min: number;
  max: number;
  classes: number;
}

/** Quantile breaks: roughly equal numbers of wards in each class. */
export function quantileClassification(values: number[], classes: number): Classification {
  const sorted = values.filter(Number.isFinite).slice().sort((a, b) => a - b);
  if (sorted.length === 0) return { method: "quantile", breaks: [], min: 0, max: 0, classes };
  const breaks: number[] = [];
  for (let i = 1; i < classes; i++) {
    const pos = (sorted.length - 1) * (i / classes);
    const lo = Math.floor(pos);
    const hi = Math.ceil(pos);
    breaks.push(sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo));
  }
  return { method: "quantile", breaks, min: sorted[0], max: sorted[sorted.length - 1], classes };
}

/** Fixed, symmetric breaks around zero for the diverging change ramp. */
export function divergingClassification(values: number[], inner: number, outer: number): Classification {
  const finite = values.filter(Number.isFinite);
  return {
    method: "fixed",
    breaks: [-outer, -inner, inner, outer],
    min: Math.min(...finite, -outer),
    max: Math.max(...finite, outer),
    classes: 5,
  };
}

/** 1-based class index for a value. */
export function classify(value: number, c: Classification): number {
  if (!Number.isFinite(value)) return 0;
  let i = 0;
  while (i < c.breaks.length && value > c.breaks[i]) i++;
  return i + 1;
}

/** Lower and upper edge for class k (1-based), for legend labels. */
export function classRange(k: number, c: Classification): [number, number] {
  const lo = k === 1 ? c.min : c.breaks[k - 2];
  const hi = k === c.classes ? c.max : c.breaks[k - 1];
  return [lo, hi];
}
