import { useSourceDrawer } from "./SourceDrawer";
import styles from "./FigureChip.module.css";

interface Props {
  /** The figure as shown, already formatted with its unit. */
  children: string;
  toolResultId: string;
  path: string;
  /** Plain description of the figure for the drawer and screen readers. */
  label?: string;
  size?: "inline" | "hero";
}

/** A verified figure: tabular value with a thin canopy underline. Opens its
 *  source on click or Enter. */
export function FigureChip({ children, toolResultId, path, label, size = "inline" }: Props) {
  const drawer = useSourceDrawer();
  const active = drawer.current?.toolResultId === toolResultId && drawer.current?.path === path;
  return (
    <button
      type="button"
      className={`${styles.chip} ${size === "hero" ? styles.hero : ""} ${active ? styles.active : ""}`}
      onClick={(e) => drawer.open({ toolResultId, path, shown: children, label }, e.currentTarget)}
      aria-label={`${label ? `${label}: ` : ""}${children}. Show source`}
      aria-expanded={active}
    >
      {children}
    </button>
  );
}
