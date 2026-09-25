import type { Weights } from "../lib/api";
import styles from "./WeightSliders.module.css";

const KEYS: { key: keyof Weights; label: string; hint: string }[] = [
  { key: "heat", label: "Surface temperature", hint: "Hotter wards score higher" },
  { key: "green", label: "Green deficit", hint: "Less vegetation scores higher" },
  { key: "built", label: "Built-up pressure", hint: "More built-up land scores higher" },
  { key: "exposure", label: "People exposed", hint: "Denser population scores higher" },
];

/** Changing one weight rescales the other three in proportion, so the four
 *  always sum to 100%. */
export function rebalance(w: Weights, key: keyof Weights, value: number): Weights {
  const v = Math.max(0, Math.min(1, value));
  const others = KEYS.map((k) => k.key).filter((k) => k !== key);
  const rest = others.reduce((s, k) => s + w[k], 0);
  const next = { ...w, [key]: v } as Weights;
  for (const k of others) next[k] = rest > 0 ? (w[k] / rest) * (1 - v) : (1 - v) / others.length;
  return next;
}

interface Props {
  weights: Weights;
  defaults: Weights;
  onChange: (w: Weights) => void;
}

export function WeightSliders({ weights, defaults, onChange }: Props) {
  const isDefault = KEYS.every((k) => Math.abs(weights[k.key] - defaults[k.key]) < 0.005);
  return (
    <fieldset className={styles.set}>
      <legend className="visually-hidden">Risk score weights</legend>
      {KEYS.map(({ key, label, hint }) => (
        <div key={key} className={styles.row}>
          <label htmlFor={`w-${key}`} className={styles.label}>
            <span>{label}</span>
            <span className={styles.pct}>{Math.round(weights[key] * 100)}%</span>
          </label>
          <input
            id={`w-${key}`}
            type="range"
            min={0}
            max={100}
            step={1}
            value={Math.round(weights[key] * 100)}
            onChange={(e) => onChange(rebalance(weights, key, Number(e.target.value) / 100))}
            className={styles.range}
            aria-describedby={`w-${key}-hint`}
          />
          <span id={`w-${key}-hint`} className={styles.hint}>
            {hint}
          </span>
        </div>
      ))}
      <button type="button" className="btn" onClick={() => onChange(defaults)} disabled={isDefault}>
        Reset to default weights
      </button>
    </fieldset>
  );
}
