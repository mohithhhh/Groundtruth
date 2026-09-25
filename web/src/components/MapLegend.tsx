import { type Classification, classRange } from "../lib/bins";
import { midSentence } from "../lib/format";
import type { MapView } from "../lib/views";
import styles from "./MapLegend.module.css";

interface Props {
  view: MapView;
  classification: Classification;
  year: number;
  season: string;
  wardCount: number;
  /** Shown when a plan's modeled result is on the map. */
  modeledNote?: string;
}

export function MapLegend({ view, classification, year, season, wardCount, modeledNote }: Props) {
  const classes = Array.from({ length: classification.classes }, (_, i) => i + 1);
  const [lo] = classRange(1, classification);
  const [, hi] = classRange(classification.classes, classification);
  return (
    <figure className={styles.legend} aria-label={`Legend: ${view.legendTitle}`}>
      <figcaption className={styles.title}>{view.legendTitle}</figcaption>
      <ol className={styles.scale}>
        {classes.map((k) => {
          const [a, b] = classRange(k, classification);
          return (
            <li key={k} className={styles.row}>
              <span className={styles.swatch} style={{ background: `var(${view.ramp[k - 1]})` }} aria-hidden="true" />
              <span className={styles.range}>
                {view.format(a)} to {view.format(b)}
              </span>
            </li>
          );
        })}
      </ol>
      {/* On narrow screens the scale collapses to one strip with its ends labelled. */}
      <p className={styles.ends} aria-hidden="true">
        <span>{view.format(lo)}</span>
        <span>{view.format(hi)}</span>
      </p>
      <p className={styles.meta}>
        {year}, {midSentence(season)}. {view.methodLabel(wardCount)}.
      </p>
      <p className={styles.note}>{modeledNote ?? view.note}</p>
    </figure>
  );
}
