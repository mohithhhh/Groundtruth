import { useQuery } from "@tanstack/react-query";
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { MapLegend } from "../components/MapLegend";
import { AllocationTable, ComparisonBlock, CostInput } from "../components/Plan";
import { ErrorState, Loading } from "../components/States";
import { type Sweep, WardMap } from "../components/WardMap";
import { api, CORPORATIONS, type Corporation, type PlanResponse } from "../lib/api";
import { classify } from "../lib/bins";
import { useCorporationShapes, useWardShapes, useWards } from "../lib/data";
import { rupees } from "../lib/format";
import { BASELINE_YEAR, CURRENT_YEAR, usePrefs, wardName } from "../lib/prefs";
import { mapViews } from "../lib/views";
import styles from "./PlanPage.module.css";

const CRORE = 1e7;

export function PlanPage() {
  const { theme, lang } = usePrefs();
  const shapes = useWardShapes();
  const corps = useCorporationShapes();
  const wards = useWards(CURRENT_YEAR);
  const catalogQ = useQuery({ queryKey: ["interventions"], queryFn: api.interventions, staleTime: Infinity });

  const [scope, setScope] = useState<Corporation | "city">("East");
  const [budgetCrore, setBudgetCrore] = useState<string>("50");
  const [costs, setCosts] = useState<Record<string, number>>({});
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sweep, setSweep] = useState<Sweep | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const sweepId = useRef(0);
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (catalogQ.data && Object.keys(costs).length === 0) {
      setCosts(Object.fromEntries(catalogQ.data.map((c) => [c.intervention_id, c.cost_amount_inr_per_unit])));
    }
  }, [catalogQ.data, costs]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3200);
    return () => clearTimeout(t);
  }, [toast]);

  const view = useMemo(() => mapViews(BASELINE_YEAR).lst, []);
  const rows = wards.data ?? [];
  const values = useMemo(() => rows.map(view.value), [rows, view]);
  const classification = useMemo(() => view.classify(values), [view, values]);
  const bins = useMemo(() => new Map(rows.map((r, i) => [r.ward_key, classify(values[i], classification)])), [rows, values, classification]);
  const catalog = useMemo(() => new Map((catalogQ.data ?? []).map((c) => [c.intervention_id, c])), [catalogQ.data]);
  const byKey = useMemo(() => new Map(rows.map((r) => [r.ward_key, r])), [rows]);

  const budget = Number(budgetCrore) * CRORE;
  const budgetValid = Number.isFinite(budget) && budget > 0;

  const run = async (e: FormEvent) => {
    e.preventDefault();
    if (!budgetValid || !catalogQ.data) return;
    setRunning(true);
    setError(null);
    const overrides = Object.fromEntries(
      catalogQ.data.filter((c) => costs[c.intervention_id] !== c.cost_amount_inr_per_unit).map((c) => [c.intervention_id, costs[c.intervention_id]]),
    );
    try {
      const result = await api.plan(budget, scope === "city" ? null : scope, overrides);
      setPlan(result);
      // Modeled class after the plan: current surface temperature plus the
      // summed modeled ward cooling, classified on the same breaks.
      const cooling = new Map<string, number>();
      for (const a of result.allocation) cooling.set(a.ward_key, (cooling.get(a.ward_key) ?? 0) + a.cooling_mid_c);
      const targets = new Map<string, number>();
      for (const [key, dc] of cooling) {
        const w = byKey.get(key);
        if (w) targets.set(key, classify(w.lst_mean_c + dc, classification));
      }
      sweepId.current += 1;
      setSweep({ id: sweepId.current, targets });
      setToast("Plan ready");
      requestAnimationFrame(() => resultRef.current?.focus());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setRunning(false);
    }
  };

  const scopeLabel = scope === "city" ? "the whole city" : `${scope} corporation`;

  return (
    <div className={styles.page}>
      <section className={styles.mapArea} aria-label="Plan map">
        {shapes.data && wards.data ? (
          <WardMap
            shapes={shapes.data}
            corporations={corps.data}
            bins={bins}
            ramp={view.ramp}
            theme={theme}
            lang={lang}
            sweep={sweep}
            tooltip={(key) => {
              const w = byKey.get(key);
              if (!w) return null;
              const funded = plan?.allocation.filter((a) => a.ward_key === key) ?? [];
              return { title: wardName(w, lang), value: funded.length ? `In this plan: ${funded.map((f) => catalog.get(f.intervention_id)?.name ?? f.intervention_id).join(", ")}` : view.format(w.lst_mean_c) };
            }}
            ariaLabel="Map of ward surface temperature. After a plan runs, funded wards are outlined in green and shaded toward their modeled temperature."
          />
        ) : (
          <div className={styles.center}>
            {shapes.error || wards.error ? <ErrorState message={(shapes.error ?? wards.error)!.message} /> : <Loading step="Loading ward boundaries and surface temperatures." />}
          </div>
        )}
        {wards.data && (
          <MapLegend
            view={view}
            classification={classification}
            year={CURRENT_YEAR}
            season="Pre-monsoon (March to May)"
            wardCount={rows.length}
            modeledNote={
              plan
                ? "Green outlines mark funded wards, shaded toward their modeled surface temperature after the plan. A modeled association, not a promise."
                : view.note
            }
          />
        )}
      </section>

      <aside className={styles.panel}>
        <form className={styles.controls} onSubmit={run} aria-labelledby="plan-title">
          <h1 id="plan-title" className={styles.title}>
            Plan a cooling budget
          </h1>
          <p className={styles.lede}>Choose where and how much. Penumbra funds the most modeled cooling per rupee, then compares it with funding the hottest wards first.</p>
          <div className={styles.row}>
            <label className="field">
              <span className="label">Where</span>
              <select className="input" value={scope} onChange={(e) => setScope(e.target.value as Corporation | "city")}>
                <option value="city">Whole city</option>
                {CORPORATIONS.map((c) => (
                  <option key={c} value={c}>
                    {c} corporation
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="label">Budget, ₹ crore</span>
              <input
                className="input"
                type="number"
                inputMode="decimal"
                min={0}
                step="any"
                value={budgetCrore}
                onChange={(e) => setBudgetCrore(e.target.value)}
                aria-describedby="budget-help"
                aria-invalid={!budgetValid}
              />
            </label>
          </div>
          <p id="budget-help" className={styles.help}>
            {budgetValid ? `${rupees(budget)} for ${scopeLabel}.` : "Enter a budget above zero."}
          </p>

          <details className={styles.costs}>
            <summary>Interventions and assumed costs</summary>
            {catalogQ.isPending && <Loading step="Loading the intervention catalog." />}
            {catalogQ.isError && <ErrorState message={catalogQ.error.message} onRetry={() => catalogQ.refetch()} />}
            <ul className={styles.costList}>
              {catalogQ.data?.map((c) => (
                <CostInput key={c.intervention_id} item={c} value={costs[c.intervention_id] ?? c.cost_amount_inr_per_unit} onChange={(v) => setCosts((s) => ({ ...s, [c.intervention_id]: v }))} />
              ))}
            </ul>
            <p className={styles.help}>Every cost is an assumed placeholder, not a vendor or BBMP quote. Edit any of them to fit your own estimates.</p>
          </details>

          <button type="submit" className="btn btn-primary" disabled={running || !budgetValid || !catalogQ.data}>
            {running ? "Running plan" : "Run plan"}
          </button>
          {running && <Loading step={`Matching interventions to every ward in ${scopeLabel} and allocating the budget.`} />}
          {error && <ErrorState message={error} />}
        </form>

        {plan && (
          <div className={styles.results} ref={resultRef} tabIndex={-1} aria-label="Plan result">
            <ComparisonBlock plan={plan} />
            <AllocationTable plan={plan} catalog={catalog} wardLabel={(a) => wardName({ ward_name: a.ward_name, ward_name_kn: byKey.get(a.ward_key)?.ward_name_kn }, lang)} />
            <section aria-labelledby="assume-title">
              <h2 id="assume-title" className={styles.h2}>
                Assumptions
              </h2>
              <ul className={styles.assumptions}>
                {plan.assumptions.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </section>
          </div>
        )}
      </aside>

      <div className={styles.toast} role="status" aria-live="polite">
        {toast && <span>{toast}</span>}
      </div>
    </div>
  );
}
