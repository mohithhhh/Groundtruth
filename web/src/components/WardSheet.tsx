import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type Brief, type Recommendation } from "../lib/api";
import { byModeledEffect, celsius, midSentence, ndvi, percent, rupees, signedCelsius } from "../lib/format";
import { type Lang, usePrefs } from "../lib/prefs";
import { FigureChip } from "./FigureChip";
import { CoverageNote, ErrorState, Loading } from "./States";
import styles from "./WardSheet.module.css";

export interface Domains {
  lst: [number, number];
  ndvi: [number, number];
  built: [number, number];
}

interface Props {
  wardKey: string;
  domains: Domains;
  onClose: () => void;
}

export function WardSheet({ wardKey, domains, onClose }: Props) {
  const { lang } = usePrefs();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const q = useQuery({ queryKey: ["brief", wardKey, lang], queryFn: () => api.brief(wardKey, lang), staleTime: 5 * 60_000 });

  useEffect(() => {
    headingRef.current?.focus();
  }, [wardKey]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !document.querySelector('[role="dialog"][aria-labelledby="source-heading"]')) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <section className={styles.sheet} aria-labelledby="ward-sheet-title">
      <button type="button" className={styles.close} onClick={onClose} aria-label="Close ward details">
        <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
          <path d="M3.5 3.5l9 9m0-9l-9 9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      </button>
      {q.isPending && (
        <div className={styles.pad}>
          <h2 id="ward-sheet-title" ref={headingRef} tabIndex={-1} className="visually-hidden">
            Ward details
          </h2>
          <Loading step="Looking up this ward's figures, its city comparison and matching interventions." />
        </div>
      )}
      {q.isError && (
        <div className={styles.pad}>
          <h2 id="ward-sheet-title" ref={headingRef} tabIndex={-1} className="visually-hidden">
            Ward details
          </h2>
          <ErrorState message={q.error.message} onRetry={() => q.refetch()} />
        </div>
      )}
      {q.data && <SheetBody brief={q.data} domains={domains} lang={lang} headingRef={headingRef} />}
    </section>
  );
}

function SheetBody({ brief, domains, lang, headingRef }: { brief: Brief; domains: Domains; lang: Lang; headingRef: React.RefObject<HTMLHeadingElement | null> }) {
  const navigate = useNavigate();
  const w = brief.ward;
  const b = brief.baseline;
  const ids = brief.tool_result_ids;
  const primary = lang === "kn" ? w.ward_name_kn : w.ward_name;
  const secondary = lang === "kn" ? w.ward_name : w.ward_name_kn;
  const diff = brief.city_median?.difference_c;
  const askText = `How hot is ${w.ward_name}, and how much green cover does it have in ${brief.year}?`;

  const modeled = byModeledEffect(brief.recommended_actions.filter((r) => r.effect_type === "modeled_association"));
  const notModeled = brief.recommended_actions.filter((r) => r.effect_type !== "modeled_association");

  return (
    <div className={styles.pad}>
      <header className={styles.header}>
        <h2 id="ward-sheet-title" ref={headingRef} tabIndex={-1} className={`${styles.name} ${lang === "kn" ? "kn" : ""}`}>
          {primary}
        </h2>
        {secondary && <p className={`${styles.alt} ${lang === "kn" ? "" : "kn"}`}>{secondary}</p>}
        <p className={styles.ac}>
          Ward {w.ward_no} in {w.corporation} corporation, {w.ac} assembly constituency
        </p>
      </header>

      <div className={styles.hero}>
        <FigureChip toolResultId={ids.ward} path="data.lst_mean_c" size="hero" label={`${brief.year} surface temperature, ${w.ward_name}`}>
          {celsius(w.lst_mean_c)}
        </FigureChip>
        <p className={styles.heroCaption}>
          Surface temperature, {midSentence(brief.season)} {brief.year}.
          {diff != null && (
            <>
              {" "}
              <FigureChip toolResultId={ids.city_median} path="data.difference_c" label="Difference from the city median ward">
                {signedCelsius(diff)}
              </FigureChip>{" "}
              {diff >= 0 ? "above" : "below"} the city median ward.
            </>
          )}
        </p>
        <p className={styles.rank}>
          Heat risk rank in the city:{" "}
          <FigureChip toolResultId={ids.ward} path="data.rank" label="Citywide heat risk rank">
            {String(w.rank)}
          </FigureChip>
          .
        </p>
      </div>

      <CoverageNote validFrac={w.valid_pixel_frac} year={brief.year} />
      {b && <CoverageNote validFrac={b.valid_pixel_frac} year={brief.baseline_year} />}

      <section className={styles.section} aria-labelledby="sm-title">
        <h3 id="sm-title" className={styles.h3}>
          {brief.baseline_year} and {brief.year}
        </h3>
        <div className={styles.multiples}>
          <Multiple
            title="Surface temperature"
            before={b?.lst_mean_c}
            after={w.lst_mean_c}
            domain={domains.lst}
            fmt={(v) => celsius(v)}
            beforeChip={b ? { id: ids.baseline, path: "data.lst_mean_c" } : null}
            afterChip={{ id: ids.ward, path: "data.lst_mean_c" }}
            change={{ value: w.delta_lst_c, id: ids.ward, path: "data.delta_lst_c", text: signedCelsius(w.delta_lst_c) }}
            years={[brief.baseline_year, brief.year]}
            warmIsBad
          />
          <Multiple
            title="Green cover (NDVI)"
            before={b?.ndvi_mean}
            after={w.ndvi_mean}
            domain={domains.ndvi}
            fmt={ndvi}
            beforeChip={b ? { id: ids.baseline, path: "data.ndvi_mean" } : null}
            afterChip={{ id: ids.ward, path: "data.ndvi_mean" }}
            change={
              brief.changes.ndvi_mean
                ? { value: brief.changes.ndvi_mean.change, id: ids.green_change, path: "data[0].change", text: signed(brief.changes.ndvi_mean.change, 2) }
                : null
            }
            years={[brief.baseline_year, brief.year]}
          />
          <Multiple
            title="Built-up share"
            before={b?.built_frac}
            after={w.built_frac}
            domain={domains.built}
            fmt={(v) => percent(v)}
            beforeChip={b ? { id: ids.baseline, path: "data.built_frac" } : null}
            afterChip={{ id: ids.ward, path: "data.built_frac" }}
            change={
              brief.changes.built_frac
                ? { value: brief.changes.built_frac.change, id: ids.built_change, path: "data[0].change", text: points(brief.changes.built_frac.change * 100) }
                : null
            }
            years={[brief.baseline_year, brief.year]}
            warmIsBad
          />
        </div>
        <p className={styles.fine}>
          Hollow dot {brief.baseline_year}, filled dot {brief.year}. Grey lines span all wards in {brief.year}. Each year is one pre-monsoon composite, so a change can reflect that season's weather.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="fac-title">
        <h3 id="fac-title" className={styles.h3}>
          Facilities in this ward
        </h3>
        <p className={styles.facilities}>
          <FigureChip toolResultId={ids.facilities} path="data.counts.hospital" label="Hospitals in this ward">
            {String(brief.facilities.counts.hospital)}
          </FigureChip>{" "}
          {brief.facilities.counts.hospital === 1 ? "hospital" : "hospitals"} and{" "}
          <FigureChip toolResultId={ids.facilities} path="data.counts.school" label="Schools in this ward">
            {String(brief.facilities.counts.school)}
          </FigureChip>{" "}
          {brief.facilities.counts.school === 1 ? "school" : "schools"}, from Overture Maps places.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="act-title">
        <h3 id="act-title" className={styles.h3}>
          Recommended actions
        </h3>
        <p className={styles.fine}>Modeled associations with surface temperature, not guaranteed outcomes. Costs are assumed until sourced.</p>
        <ul className={styles.actions}>
          {modeled.map((r) => (
            <Action key={r.intervention_id} r={r} index={brief.recommended_actions.indexOf(r)} brief={brief} />
          ))}
          {notModeled.map((r) => (
            <Action key={r.intervention_id} r={r} index={brief.recommended_actions.indexOf(r)} brief={brief} />
          ))}
        </ul>
      </section>

      <div className={styles.buttons}>
        <Link className="btn btn-primary" to={`/brief/${encodeURIComponent(w.ward_key)}?lang=${lang}`}>
          Export ward brief
        </Link>
        <button type="button" className="btn" onClick={() => navigate(`/ask?q=${encodeURIComponent(askText)}`)}>
          Ask about this ward
        </button>
      </div>
      {brief.unverified_translation && <p className={styles.fine}>Kannada labels are translated for this interface and have not been reviewed by a certified translator.</p>}
    </div>
  );
}

function points(v: number): string {
  const r = Math.round(v);
  return `${signed(v, 0)} ${Math.abs(r) === 1 ? "point" : "points"}`;
}

function signed(v: number, digits: number): string {
  const r = Number(v.toFixed(digits));
  return `${r > 0 ? "+" : r < 0 ? "−" : ""}${Math.abs(r).toFixed(digits)}`;
}

function Action({ r, index, brief }: { r: Recommendation; index: number; brief: Brief }) {
  const id = brief.tool_result_ids.interventions;
  const base = `data.recommendations[${index}]`;
  const doc = (docId: string) => brief.guidance_documents.find((d) => d.doc_id === docId);
  return (
    <li className={styles.action}>
      <div className={styles.actionHead}>
        <span className={styles.actionName}>{r.name}</span>
        <span className={`${styles.tag} ${r.effect_type === "modeled_association" ? styles.tagModeled : ""}`}>
          {r.effect_type === "modeled_association" ? "Modeled" : "Cooling not modeled"}
        </span>
      </div>
      {r.effect_type === "modeled_association" && r.effect_low_c != null && r.effect_high_c != null ? (
        <p className={styles.effect}>
          {signedCelsius(r.effect_high_c, 2) === signedCelsius(r.effect_low_c, 2) ? (
            <>
              about{" "}
              <FigureChip toolResultId={id} path={`${base}.effect_mid_c`} label={`${r.name}: modeled effect`}>
                {signedCelsius(r.effect_mid_c ?? r.effect_low_c, 2)}
              </FigureChip>
            </>
          ) : (
            <>
              <FigureChip toolResultId={id} path={`${base}.effect_high_c`} label={`${r.name}: smaller end of modeled effect`}>
                {signedCelsius(r.effect_high_c, 2)}
              </FigureChip>{" "}
              to{" "}
              <FigureChip toolResultId={id} path={`${base}.effect_low_c`} label={`${r.name}: larger end of modeled effect`}>
                {signedCelsius(r.effect_low_c, 2)}
              </FigureChip>
            </>
          )}{" "}
          ward surface temperature per {r.unit.replace(/^1 /, "")}
        </p>
      ) : (
        <p className={styles.effect}>
          Our model has no term for how this works, so it gives no ward-level estimate.
          {r.cited_fact ? ` Published evidence: ${r.cited_fact}` : ""}
        </p>
      )}
      <p className={styles.cost}>
        Assumed cost{" "}
        <FigureChip toolResultId={id} path={`${base}.cost_inr_per_unit`} label={`${r.name}: assumed cost per unit`}>
          {rupees(r.cost_inr_per_unit)}
        </FigureChip>{" "}
        per {r.unit.replace(/^1 /, "")}
      </p>
      {r.citations.map((c) => {
        const d = doc(c.doc_id);
        return (
          <details key={`${c.doc_id}-${c.page}`} className={styles.cite}>
            <summary>
              {d ? `${d.publisher}, ${d.doc_date.slice(0, 4)}` : c.doc_id}, page {c.page}
            </summary>
            <blockquote>{c.quote}</blockquote>
            {d && (
              <a href={d.url} target="_blank" rel="noreferrer">
                {d.title}
              </a>
            )}
          </details>
        );
      })}
    </li>
  );
}

interface ChipRef {
  id: string;
  path: string;
}

function Multiple(props: {
  title: string;
  before: number | undefined;
  after: number;
  domain: [number, number];
  fmt: (v: number) => string;
  beforeChip: ChipRef | null;
  afterChip: ChipRef;
  change: { value: number; id: string; path: string; text: string } | null;
  years: [number, number];
  warmIsBad?: boolean;
}) {
  const { title, before, after, fmt, beforeChip, afterChip, change, years, warmIsBad } = props;
  const lo = Math.min(props.domain[0], before ?? after, after);
  const hi = Math.max(props.domain[1], before ?? after, after);
  const x = (v: number) => 6 + ((v - lo) / (hi - lo || 1)) * 188;
  const worse = change ? (warmIsBad ? change.value > 0 : change.value < 0) : false;
  return (
    <div className={styles.multiple}>
      <p className={styles.mTitle}>{title}</p>
      <svg viewBox="0 0 200 22" className={styles.dumbbell} role="img" aria-label={`${title}: ${before != null ? `${fmt(before)} in ${years[0]}, ` : ""}${fmt(after)} in ${years[1]}`}>
        <line x1="6" x2="194" y1="11" y2="11" className={styles.axis} />
        {before != null && <line x1={x(before)} x2={x(after)} y1="11" y2="11" className={worse ? styles.linkWorse : styles.linkBetter} />}
        {before != null && <circle cx={x(before)} cy="11" r="4.5" className={styles.dotBefore} />}
        <circle cx={x(after)} cy="11" r="5" className={styles.dotAfter} />
      </svg>
      <p className={styles.mValues}>
        <span>
          {years[0]}{" "}
          {before != null && beforeChip ? (
            <FigureChip toolResultId={beforeChip.id} path={beforeChip.path} label={`${title}, ${years[0]}`}>
              {fmt(before)}
            </FigureChip>
          ) : (
            "not available"
          )}
        </span>
        <span>
          {years[1]}{" "}
          <FigureChip toolResultId={afterChip.id} path={afterChip.path} label={`${title}, ${years[1]}`}>
            {fmt(after)}
          </FigureChip>
        </span>
        {change && (
          <span className={styles.mChange}>
            Change{" "}
            <FigureChip toolResultId={change.id} path={change.path} label={`${title}, change`}>
              {change.text}
            </FigureChip>
          </span>
        )}
      </p>
    </div>
  );
}
