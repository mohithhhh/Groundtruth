// Number formatting. Every figure keeps its unit; Indian digit grouping for
// rupees and people, since the audience plans in lakh and crore.

const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const count = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

export function celsius(v: number, digits = 1): string {
  return `${v.toFixed(digits)} °C`;
}

export function signedCelsius(v: number, digits = 1): string {
  const rounded = Number(v.toFixed(digits));
  const sign = rounded > 0 ? "+" : rounded < 0 ? "−" : "";
  return `${sign}${Math.abs(rounded).toFixed(digits)} °C`;
}

export function ndvi(v: number): string {
  return v.toFixed(2);
}

export function percent(frac: number, digits = 0): string {
  return `${(frac * 100).toFixed(digits)}%`;
}

export function rupees(v: number): string {
  return `₹${inr.format(Math.round(v))}`;
}

/** Short rupee form for headings and inputs: ₹50 crore, ₹4 lakh. */
export function rupeesShort(v: number): string {
  if (v >= 1e7) return `₹${trim(v / 1e7)} crore`;
  if (v >= 1e5) return `₹${trim(v / 1e5)} lakh`;
  return rupees(v);
}

function trim(v: number): string {
  return v >= 100 ? v.toFixed(0) : Number(v.toFixed(2)).toString();
}

export function people(v: number): string {
  return count.format(Math.round(v));
}

export function personC(v: number): string {
  return `${count.format(Math.round(v))} person-°C`;
}

export function score(v: number): string {
  return v.toFixed(2);
}

export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function seconds(v: number): string {
  return v < 1 ? `${Math.round(v * 1000)} ms` : `${v.toFixed(1)} s`;
}

/** "Pre-monsoon (March to May)" -> "pre-monsoon (March to May)" for mid-sentence use. */
export function midSentence(s: string): string {
  return s.charAt(0).toLowerCase() + s.slice(1);
}

/** "−0.58 °C to −0.61 °C", or "about −0.01 °C" when both ends round the same. */
export function celsiusRange(smaller: number, larger: number, digits = 2): string {
  const a = signedCelsius(smaller, digits);
  const b = signedCelsius(larger, digits);
  return a === b ? `about ${a}` : `${a} to ${b}`;
}

/** Modeled interventions first, largest cooling first; then the unmodeled ones. */
export function byModeledEffect<T extends { effect_mid_c: number | null }>(items: T[]): T[] {
  return [...items].sort((x, y) => {
    if (x.effect_mid_c == null && y.effect_mid_c == null) return 0;
    if (x.effect_mid_c == null) return 1;
    if (y.effect_mid_c == null) return -1;
    return x.effect_mid_c - y.effect_mid_c;
  });
}
