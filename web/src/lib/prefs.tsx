import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type Theme = "light" | "dark";
export type Lang = "en" | "kn";

interface Prefs {
  theme: Theme;
  toggleTheme: () => void;
  lang: Lang;
  setLang: (l: Lang) => void;
  year: number;
  setYear: (y: number) => void;
}

const PrefsContext = createContext<Prefs | null>(null);

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* private mode: preference just won't persist */
  }
}

function systemTheme(): Theme {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export const CURRENT_YEAR = 2025;
export const BASELINE_YEAR = 2016;

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = read("groundtruth.theme");
    return saved === "light" || saved === "dark" ? saved : systemTheme();
  });
  const [lang, setLangState] = useState<Lang>(() => (read("groundtruth.lang") === "kn" ? "kn" : "en"));
  const [year, setYear] = useState<number>(CURRENT_YEAR);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((t) => {
      const next = t === "dark" ? "light" : "dark";
      write("groundtruth.theme", next);
      return next;
    });
  }, []);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    write("groundtruth.lang", l);
  }, []);

  const value = useMemo(() => ({ theme, toggleTheme, lang, setLang, year, setYear }), [theme, toggleTheme, lang, setLang, year]);
  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}

export function usePrefs(): Prefs {
  const ctx = useContext(PrefsContext);
  if (!ctx) throw new Error("usePrefs outside PrefsProvider");
  return ctx;
}

/** Ward name in the reader's chosen script. */
export function wardName(w: { ward_name: string; ward_name_kn?: string | null }, lang: Lang): string {
  return lang === "kn" && w.ward_name_kn ? w.ward_name_kn : w.ward_name;
}
