import { NavLink } from "react-router-dom";
import { BASELINE_YEAR, CURRENT_YEAR, usePrefs } from "../lib/prefs";
import styles from "./TopBar.module.css";

const NAV = [
  { to: "/", label: "Map", end: true },
  { to: "/ask", label: "Ask", end: false },
  { to: "/plan", label: "Plan", end: false },
  { to: "/method", label: "Method", end: false },
];

export function Mark({ size = 22 }: { size?: number }) {
  // Umbra, penumbra and a sliver of light: the product's idea in one glyph.
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className={styles.mark}>
      <defs>
        <radialGradient id="pm-shade" cx="0.66" cy="0.34" r="0.78">
          <stop offset="0.28" stopColor="var(--heat-3)" />
          <stop offset="0.58" stopColor="var(--accent)" stopOpacity="0.55" />
          <stop offset="1" stopColor="var(--text)" />
        </radialGradient>
      </defs>
      <circle cx="16" cy="16" r="14" fill="url(#pm-shade)" />
    </svg>
  );
}

export function TopBar() {
  return (
    <header className={styles.bar}>
      <NavLink to="/" className={styles.brand} aria-label="Penumbra, map home">
        <Mark />
        <span className={styles.wordmark}>Penumbra</span>
      </NavLink>
      <nav className={styles.nav} aria-label="Main">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ""}`}>
            {n.label}
          </NavLink>
        ))}
      </nav>
      <div className={styles.tools}>
        <span className={styles.city}>Bengaluru</span>
        <CityYearSwitch />
        <LangToggle />
        <ThemeToggle />
      </div>
    </header>
  );
}

export function CityYearSwitch() {
  const { year, setYear } = usePrefs();
  return (
    <label className={styles.year}>
      <span className="visually-hidden">Data year</span>
      <select value={year} onChange={(e) => setYear(Number(e.target.value))} className={styles.select}>
        <option value={CURRENT_YEAR}>{CURRENT_YEAR}</option>
        <option value={BASELINE_YEAR}>{BASELINE_YEAR}</option>
      </select>
    </label>
  );
}

export function LangToggle() {
  const { lang, setLang } = usePrefs();
  return (
    <div className={styles.segment} role="radiogroup" aria-label="Ward names in">
      <button type="button" role="radio" aria-checked={lang === "en"} className={lang === "en" ? styles.segOn : ""} onClick={() => setLang("en")}>
        EN
      </button>
      <button
        type="button"
        role="radio"
        aria-checked={lang === "kn"}
        lang="kn"
        className={`kn ${lang === "kn" ? styles.segOn : ""}`}
        onClick={() => setLang("kn")}
        aria-label="Kannada"
      >
        ಕ
      </button>
    </div>
  );
}

export function ThemeToggle() {
  const { theme, toggleTheme } = usePrefs();
  const next = theme === "dark" ? "light" : "dark";
  return (
    <button type="button" className={styles.icon} onClick={toggleTheme} aria-label={`Switch to ${next} theme`} title={`Switch to ${next} theme`}>
      <svg width="18" height="18" viewBox="0 0 20 20" aria-hidden="true">
        <circle cx="10" cy="10" r="7.25" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <path d="M10 2.75a7.25 7.25 0 0 1 0 14.5z" fill="currentColor" />
      </svg>
    </button>
  );
}
