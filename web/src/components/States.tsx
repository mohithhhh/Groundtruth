import type { ReactNode } from "react";
import styles from "./States.module.css";

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className={styles.empty}>
      <p className={styles.title}>{title}</p>
      {children && <div className={styles.body}>{children}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className={styles.error} role="alert">
      <p>{message}</p>
      {onRetry && (
        <button type="button" className="btn" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

/** Names the real step being waited on -- no generic spinner. */
export function Loading({ step }: { step: string }) {
  return (
    <p className={styles.loading} role="status">
      <span className={styles.pulse} aria-hidden="true" />
      {step}
    </p>
  );
}

export function CoverageNote({ validFrac, year }: { validFrac: number; year: number }) {
  if (validFrac >= 0.5) return null;
  return (
    <p className={styles.coverage} role="note">
      Clouds hid most of this ward in the {year} images, so its value for {year} is uncertain.
    </p>
  );
}
