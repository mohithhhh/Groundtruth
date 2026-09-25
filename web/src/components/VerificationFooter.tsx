import type { AskResponse } from "../lib/api";
import styles from "./VerificationFooter.module.css";

export function Check() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="8" r="7.25" fill="currentColor" />
      <path d="M4.6 8.2l2.2 2.2 4.6-4.8" fill="none" stroke="var(--panel)" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Warn() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M8 1.5l7 12.5H1z" fill="currentColor" />
      <path d="M8 6v3.6M8 11.6v.1" stroke="var(--panel)" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function reasonText(reason: string): string {
  if (reason.startsWith("stray number")) return "a number appeared without a source";
  if (reason.startsWith("could not resolve")) return "its cited field was not in the tool result";
  if (reason.startsWith("claim says")) return `it did not match the data (${reason.replace(/^claim says /, "")})`;
  if (reason === "unknown tool_result_id") return "it cited a tool result that does not exist";
  if (reason === "no matching claim") return "it had no citation";
  return reason;
}

export function VerificationFooter({ verification }: { verification: AskResponse["verification"] }) {
  const { verified, total, removed } = verification;
  const all = removed.length === 0 && total > 0;
  if (total === 0) {
    return <p className={styles.footer}>This answer states no figures, so there was nothing to verify.</p>;
  }
  return (
    <div className={`${styles.footer} ${all ? styles.ok : styles.partial}`}>
      <p className={styles.line}>
        {all ? <Check /> : <Warn />}
        <span>
          {verified} of {total} figures verified
        </span>
      </p>
      {removed.length > 0 && (
        <details className={styles.removed}>
          <summary>
            {removed.length} {removed.length === 1 ? "figure was" : "figures were"} removed before you saw them
          </summary>
          <ul>
            {removed.map((r, i) => (
              <li key={i}>Removed because {reasonText(r.reason)}.</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
