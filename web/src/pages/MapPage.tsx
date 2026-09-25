import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { MapLegend } from "../components/MapLegend";
import { RankedList, type RankedRow } from "../components/RankedList";
import { ErrorState, Loading } from "../components/States";
import { ViewSwitch } from "../components/ViewSwitch";
import { WardMap } from "../components/WardMap";
import { type Domains, WardSheet } from "../components/WardSheet";
import { WeightSliders } from "../components/WeightSliders";
import { api, CORPORATIONS, type WardRow, type Weights } from "../lib/api";
import { classify } from "../lib/bins";
import { useCorporationShapes, useWardShapes, useWards } from "../lib/data";
import { BASELINE_YEAR, CURRENT_YEAR, usePrefs, wardName } from "../lib/prefs";
import { defaultWeights, useResults } from "../lib/results";
import { mapViews, type ViewId } from "../lib/views";
import styles from "./MapPage.module.css";

const SEASON = "Pre-monsoon (March to May)";

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function sameWeights(a: Weights | null, b: Weights | null) {
  if (!a || !b) return true;
  return (Object.keys(a) as (keyof Weights)[]).every((k) => Math.abs(a[k] - b[k]) < 0.005);
}

export function MapPage() {
  const { year, lang, theme } = usePrefs();
  const [params, setParams] = useSearchParams();
  const selectedKey = params.get("ward");
  const [viewId, setViewId] = useState<ViewId>("risk");
  const [corporation, setCorporation] = useState<string>("all");
  const [showWeights, setShowWeights] = useState(false);

  const shapes = useWardShapes();
  const corps = useCorporationShapes();
  const wards = useWards(year);
  const current = useWards(CURRENT_YEAR); // for the ward sheet's city-range scales
  const results = useResults();
  const defaults = defaultWeights(results.data);
  const [weights, setWeights] = useState<Weights | null>(null);
  const w = weights ?? defaults;
  const debounced = useDebounced(w, 250);
  const reweighting = !sameWeights(debounced, defaults);

  const risk = useQuery({
    queryKey: ["risk", year, debounced],
    queryFn: () => api.risk(year, debounced!),
    enabled: reweighting && !!debounced,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (year === BASELINE_YEAR && viewId === "change") setViewId("risk");
  }, [year, viewId]);

  const views = useMemo(() => mapViews(BASELINE_YEAR), []);
  const view = views[viewId];

  const riskByKey = useMemo(() => {
    if (!reweighting || !risk.data) return null;
    return new Map(risk.data.map((r) => [r.ward_key, r.composite_risk]));
  }, [reweighting, risk.data]);

  const valueOf = useCallback(
    (key: string, fallback: number) => (viewId === "risk" && riskByKey ? (riskByKey.get(key) ?? fallback) : fallback),
    [viewId, riskByKey],
  );

  const rows = wards.data ?? [];
  const values = useMemo(() => rows.map((r) => valueOf(r.ward_key, view.value(r))), [rows, view, valueOf]);
  const classification = useMemo(() => view.classify(values), [view, values]);
  const bins = useMemo(() => {
    const m = new Map<string, number>();
    rows.forEach((r, i) => m.set(r.ward_key, classify(values[i], classification)));
    return m;
  }, [rows, values, classification]);

  const ranked: RankedRow[] = useMemo(() => {
    const list = rows
      .map((r, i) => ({ ward_key: r.ward_key, ward_name: r.ward_name, ward_name_kn: r.ward_name_kn, corporation: r.corporation, value: values[i] }))
      .filter((r) => corporation === "all" || r.corporation === corporation);
    return list.sort((a, b) => (view.higherIsWorse ? b.value - a.value : a.value - b.value));
  }, [rows, values, corporation, view]);

  const domains: Domains | null = useMemo(() => {
    const c = current.data;
    if (!c?.length) return null;
    const range = (f: (r: WardRow) => number): [number, number] => [Math.min(...c.map(f)), Math.max(...c.map(f))];
    return { lst: range((r) => r.lst_mean_c), ndvi: range((r) => r.ndvi_mean), built: range((r) => r.built_frac) };
  }, [current.data]);

  const byKey = useMemo(() => new Map(rows.map((r, i) => [r.ward_key, { r, v: values[i] }])), [rows, values]);
  const tooltip = useCallback(
    (key: string) => {
      const hit = byKey.get(key);
      return hit ? { title: wardName(hit.r, lang), value: `${view.label}: ${view.format(hit.v)}` } : null;
    },
    [byKey, lang, view],
  );

  const select = useCallback(
    (key: string) => {
      const next = new URLSearchParams(params);
      next.set("ward", key);
      setParams(next, { replace: true });
    },
    [params, setParams],
  );
  const closeSheet = useCallback(() => {
    const next = new URLSearchParams(params);
    next.delete("ward");
    setParams(next, { replace: true });
  }, [params, setParams]);

  const listTitle =
    viewId === "green" ? "Wards by green cover, least first" : viewId === "change" ? `Wards by warming since ${BASELINE_YEAR}` : `Wards by ${view.label.toLowerCase()}`;
  const scope = corporation === "all" ? "the city" : `${corporation} corporation`;
  const loadError = shapes.error ?? wards.error;

  return (
    <div className={styles.page}>
      <section className={styles.mapArea} aria-label="Ward map">
        {shapes.data && wards.data ? (
          <WardMap
            shapes={shapes.data}
            corporations={corps.data}
            bins={bins}
            ramp={view.ramp}
            theme={theme}
            lang={lang}
            selectedKey={selectedKey}
            onSelect={select}
            tooltip={tooltip}
            ariaLabel={`Map of ${rows.length} Bengaluru wards coloured by ${view.label.toLowerCase()}, ${year}. Use the ranked list to choose a ward with the keyboard.`}
          />
        ) : loadError ? (
          <div className={styles.center}>
            <ErrorState message={loadError.message} onRetry={() => (shapes.error ? shapes.refetch() : wards.refetch())} />
          </div>
        ) : (
          <div className={styles.center}>
            <Loading step={`Loading ward boundaries and ${year} satellite metrics.`} />
          </div>
        )}
        <div className={styles.viewSwitch}>
          <ViewSwitch views={views} value={viewId} onChange={setViewId} disabled={year === BASELINE_YEAR ? ["change"] : []} />
        </div>
        {wards.data && (
          <MapLegend
            view={view}
            classification={classification}
            year={year}
            season={SEASON}
            wardCount={rows.length}
            modeledNote={viewId === "risk" && reweighting ? "Using your adjusted weights. Reset them to see the default score." : undefined}
          />
        )}
        {selectedKey && domains && <WardSheet key={selectedKey} wardKey={selectedKey} domains={domains} onClose={closeSheet} />}
      </section>

      <aside className={styles.panel} aria-labelledby="ranked-title">
        <div className={styles.panelHead}>
          <h1 id="ranked-title" className={styles.title}>
            {listTitle}
          </h1>
          <div className={styles.filters}>
            <label className={styles.filter}>
              <span className="label">Corporation</span>
              <select className="input" value={corporation} onChange={(e) => setCorporation(e.target.value)}>
                <option value="all">All corporations</option>
                {CORPORATIONS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className={styles.count}>
            {ranked.length} wards in {scope}, {year}. Rank is position in this list.
            {viewId === "risk" && reweighting && risk.isFetching ? " Re-ranking with your weights." : ""}
          </p>
        </div>
        <div className={styles.listWrap}>
          {wards.data && <RankedList rows={ranked} format={view.format} lang={lang} selectedKey={selectedKey} onSelect={select} diverging={viewId === "change"} />}
        </div>
        {viewId === "risk" && w && defaults && (
          <div className={styles.weights}>
            <button type="button" className={styles.disclosure} aria-expanded={showWeights} onClick={() => setShowWeights((s) => !s)}>
              <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" className={showWeights ? styles.chevOpen : styles.chev}>
                <path d="M4 2.5L7.5 6 4 9.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Adjust weights
            </button>
            {showWeights && (
              <div className={styles.weightsBody}>
                <WeightSliders weights={w} defaults={defaults} onChange={setWeights} />
                {risk.isError && <ErrorState message={risk.error.message} />}
              </div>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}
