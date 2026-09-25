import type { TraceStep } from "../lib/api";
import { seconds } from "../lib/format";
import styles from "./AgentTrace.module.css";

/** A real sequence of what the agents did, in order, with durations. */
export function AgentTrace({ steps }: { steps: TraceStep[] }) {
  return (
    <ol className={styles.trace}>
      {steps.map((s) => (
        <li key={s.step} className={styles.step}>
          <span className={styles.n}>{s.step}</span>
          <span className={styles.desc}>{s.description}</span>
          <span className={styles.dur}>{seconds(s.duration_s)}</span>
        </li>
      ))}
    </ol>
  );
}
