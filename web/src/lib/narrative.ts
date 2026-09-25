// Splits a verified answer's template ("Ward {c1} warmed by {c2}.") into
// text runs and claim references, so each verified figure renders as a chip.

export type Segment = { kind: "text"; text: string } | { kind: "claim"; id: string };

const PLACEHOLDER = /\{(c\d+)\}/g;

export function splitTemplate(template: string): Segment[] {
  const out: Segment[] = [];
  let last = 0;
  for (const m of template.matchAll(PLACEHOLDER)) {
    const start = m.index ?? 0;
    if (start > last) out.push({ kind: "text", text: template.slice(last, start) });
    out.push({ kind: "claim", id: m[1] });
    last = start + m[0].length;
  }
  if (last < template.length) out.push({ kind: "text", text: template.slice(last) });
  return out;
}
