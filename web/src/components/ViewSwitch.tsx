import { type MapView, VIEW_ORDER, type ViewId } from "../lib/views";
import styles from "./ViewSwitch.module.css";

interface Props {
  views: Record<ViewId, MapView>;
  value: ViewId;
  onChange: (id: ViewId) => void;
  disabled?: ViewId[];
}

/** Segmented control for what the map colours by. */
export function ViewSwitch({ views, value, onChange, disabled = [] }: Props) {
  return (
    <div className={styles.switch} role="radiogroup" aria-label="Colour the map by">
      {VIEW_ORDER.map((id) => (
        <button
          key={id}
          type="button"
          role="radio"
          aria-checked={value === id}
          disabled={disabled.includes(id)}
          className={`${styles.option} ${value === id ? styles.on : ""}`}
          onClick={() => onChange(id)}
        >
          {views[id].label}
        </button>
      ))}
    </div>
  );
}
