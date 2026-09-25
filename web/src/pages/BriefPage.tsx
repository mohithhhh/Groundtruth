import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ErrorState, Loading } from "../components/States";
import { Mark } from "../components/TopBar";
import { api, type Brief } from "../lib/api";
import { byModeledEffect, celsius, celsiusRange, dateTime, midSentence, ndvi, people, percent, rupees, signedCelsius } from "../lib/format";
import styles from "./BriefPage.module.css";

export function BriefPage() {
  const { wardKey = "" } = useParams();
  const [params] = useSearchParams();
  const lang = params.get("lang") === "kn" ? "kn" : "en";
  const q = useQuery({ queryKey: ["brief", wardKey, lang], queryFn: () => api.brief(wardKey, lang) });

  useEffect(() => {
    if (q.data) document.title = `${q.data.ward.ward_name} ward brief, Groundtruth`;
    return () => {
      document.title = "Groundtruth — ward heat planning for Bengaluru";
    };
  }, [q.data]);

  return (
    <div className={styles.screen}>
      <div className={styles.toolbar}>
        <Link to={`/?ward=${encodeURIComponent(wardKey)}`} className="btn">
          Back to the map
        </Link>
        <div className={styles.toolbarRight}>
          <Link className="btn" to={`/brief/${encodeURIComponent(wardKey)}?lang=${lang === "en" ? "kn" : "en"}`}>
            {lang === "en" ? "ಕನ್ನಡ ಶೀರ್ಷಿಕೆಗಳು" : "English labels"}
          </Link>
          <button type="button" className="btn btn-primary" onClick={() => window.print()} disabled={!q.data}>
            Print or save as PDF
          </button>
        </div>
      </div>
      {q.isPending && (
        <div className={styles.paper}>
          <Loading step="Assembling this ward's figures, recommended actions and sources." />
        </div>
      )}
      {q.isError && (
        <div className={styles.paper}>
          <ErrorState message={q.error.message} onRetry={() => q.refetch()} />
        </div>
      )}
      {q.data && <Paper b={q.data} />}
    </div>
  );
}

function pointsText(v: number): string {
  const r = Math.round(v);
  return `${r > 0 ? "+" : r < 0 ? "−" : ""}${Math.abs(r)} ${Math.abs(r) === 1 ? "point" : "points"}`;
}

function Paper({ b }: { b: Brief }) {
  const w = b.ward;
  const L = b.labels;
  const ids = b.tool_result_ids;
  // Footnote numbers follow the order sources were queried.
  const note = (id: string) => b.sources.findIndex((s) => s.tool_result_id === id) + 1;
  const Fn = ({ id }: { id: string }) => <sup className={styles.fn}>{note(id)}</sup>;
  const doc = (docId: string) => b.guidance_documents.find((d) => d.doc_id === docId);

  return (
    <article className={styles.paper} lang={b.lang === "kn" ? "kn" : "en"}>
      <header className={styles.head}>
        <div className={styles.brand}>
          <Mark size={20} />
          <span>Groundtruth</span>
        </div>
        <p className={`${styles.kind} ${b.lang === "kn" ? "kn" : ""}`}>{L.ward_brief}</p>
      </header>

      <h1 className={styles.name}>{w.ward_name}</h1>
      <p className={`${styles.nameKn} kn`} lang="kn">
        {w.ward_name_kn}
      </p>
      <p className={styles.meta}>
        <span className={b.lang === "kn" ? "kn" : ""}>{L.corporation}</span>: {w.corporation}. Ward {w.ward_no}, {w.ac} assembly constituency. Data {midSentence(b.season)}{" "}
        {b.year}, compared with {b.baseline_year}.
      </p>

      <section className={styles.section}>
        <h2 className={`${styles.h2} ${b.lang === "kn" ? "kn" : ""}`}>{L.key_figures}</h2>
        <div className={styles.figures}>
          <div className={styles.fig}>
            <p className={styles.big}>
              {celsius(w.lst_mean_c)}
              <Fn id={ids.ward} />
            </p>
            <p className={styles.figLabel}>Surface temperature, {b.year}</p>
          </div>
          {b.city_median && (
            <div className={styles.fig}>
              <p className={styles.big}>
                {signedCelsius(b.city_median.difference_c)}
                <Fn id={ids.city_median} />
              </p>
              <p className={styles.figLabel}>Against the city median ward</p>
            </div>
          )}
          <div className={styles.fig}>
            <p className={styles.big}>
              {w.rank}
              <Fn id={ids.ward} />
            </p>
            <p className={styles.figLabel}>Citywide heat risk rank</p>
          </div>
        </div>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col" />
              <th scope="col">{b.baseline_year}</th>
              <th scope="col">{b.year}</th>
              <th scope="col">Change</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">Surface temperature</th>
              <td>{b.baseline ? celsius(b.baseline.lst_mean_c) : "not available"}<Fn id={ids.baseline} /></td>
              <td>{celsius(w.lst_mean_c)}<Fn id={ids.ward} /></td>
              <td>{signedCelsius(w.delta_lst_c)}<Fn id={ids.ward} /></td>
            </tr>
            <tr>
              <th scope="row">Green cover (NDVI)</th>
              <td>{b.baseline ? ndvi(b.baseline.ndvi_mean) : "not available"}<Fn id={ids.baseline} /></td>
              <td>{ndvi(w.ndvi_mean)}<Fn id={ids.ward} /></td>
              <td>{b.changes.ndvi_mean ? `${b.changes.ndvi_mean.change >= 0 ? "+" : "−"}${Math.abs(b.changes.ndvi_mean.change).toFixed(2)}` : "not available"}<Fn id={ids.green_change} /></td>
            </tr>
            <tr>
              <th scope="row">Built-up share</th>
              <td>{b.baseline ? percent(b.baseline.built_frac) : "not available"}<Fn id={ids.baseline} /></td>
              <td>{percent(w.built_frac)}<Fn id={ids.ward} /></td>
              <td>{b.changes.built_frac ? pointsText(b.changes.built_frac.change * 100) : "not available"}<Fn id={ids.built_change} /></td>
            </tr>
            <tr>
              <th scope="row">People</th>
              <td colSpan={3}>
                {people(w.population)} ({w.population_source_year} Census, apportioned to the {b.year} ward)
                <Fn id={ids.ward} />
              </td>
            </tr>
            <tr>
              <th scope="row">Facilities</th>
              <td colSpan={3}>
                {b.facilities.counts.hospital} hospitals and {b.facilities.counts.school} schools
                <Fn id={ids.facilities} />
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section className={styles.section}>
        <h2 className={`${styles.h2} ${b.lang === "kn" ? "kn" : ""}`}>{L.recommended_actions}</h2>
        <ol className={styles.actions}>
          {byModeledEffect(b.recommended_actions).map((r) => (
            <li key={r.intervention_id}>
              <p className={styles.actionName}>{r.name}</p>
              <p>
                {r.effect_low_c != null && r.effect_high_c != null
                  ? `Modeled change in ward surface temperature: ${celsiusRange(r.effect_high_c, r.effect_low_c)} per ${r.unit.replace(/^1 /, "")}.`
                  : `Cooling not modeled for this ward.${r.cited_fact ? ` Published evidence: ${r.cited_fact}` : ""}`}
                <Fn id={ids.interventions} />
              </p>
              <p>
                Assumed cost {rupees(r.cost_inr_per_unit)} per {r.unit.replace(/^1 /, "")}.
              </p>
              {r.citations.map((c) => {
                const d = doc(c.doc_id);
                return (
                  <p key={c.doc_id} className={styles.cite}>
                    “{c.quote}” {d ? `${d.publisher}, ${d.title} (${d.doc_date.slice(0, 4)})` : c.doc_id}, p. {c.page}.
                  </p>
                );
              })}
            </li>
          ))}
        </ol>
      </section>

      <section className={styles.section}>
        <h2 className={`${styles.h2} ${b.lang === "kn" ? "kn" : ""}`}>{L.assumptions}</h2>
        <ul className={styles.list}>
          <li>Effects are modeled associations with surface temperature, not guaranteed outcomes.</li>
          <li>All costs are assumed placeholders until replaced with real quotes.</li>
        </ul>
      </section>

      <section className={styles.section}>
        <h2 className={`${styles.h2} ${b.lang === "kn" ? "kn" : ""}`}>{L.limitations}</h2>
        <ul className={styles.list}>
          {b.limitations.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </section>

      <section className={styles.section}>
        <h2 className={`${styles.h2} ${b.lang === "kn" ? "kn" : ""}`}>{L.sources}</h2>
        <ol className={styles.sources}>
          {b.sources.map((s) => (
            <li key={s.tool_result_id}>
              {s.description}. Record {s.tool_result_id}, computed {dateTime(s.created_at)}.
            </li>
          ))}
        </ol>
        {b.guidance_documents.map((d) => (
          <p key={d.doc_id} className={styles.doc}>
            {d.publisher}. {d.title}. {d.doc_date.slice(0, 4)}. {d.url}
          </p>
        ))}
      </section>

      <footer className={styles.foot}>
        <span className={b.lang === "kn" ? "kn" : ""}>{L.generated}</span>: {dateTime(b.generated_at)}.
        {b.unverified_translation && " Kannada section labels have not been reviewed by a certified translator."}
      </footer>
    </article>
  );
}
