import { Link } from "react-router-dom";
import { ErrorState, Loading } from "../components/States";
import { celsius, dateTime, people, percent, personC, rupeesShort, signedCelsius } from "../lib/format";
import { BASELINE_YEAR, CURRENT_YEAR } from "../lib/prefs";
import { type Results, useResults } from "../lib/results";
import styles from "./MethodPage.module.css";

const SOURCES = [
  {
    name: "Ward boundaries and population",
    detail: "OpenCity, GBA final ward map with population, December 2025. Population figures are 2011 Census counts apportioned to the 2025 wards.",
    license: "Listed as Other (Public Domain) on OpenCity",
  },
  {
    name: "Surface temperature and green cover",
    detail: `USGS Landsat 8 and 9, Collection 2 Level 2, through Google Earth Engine. Cloud-masked median composites for March to May of ${BASELINE_YEAR} and ${CURRENT_YEAR}, at 30 m.`,
    license: "Public domain, courtesy of the U.S. Geological Survey",
  },
  {
    name: "Built-up share and water",
    detail: "Google Dynamic World V1, for the same seasons.",
    license: "CC BY 4.0. Produced for the Dynamic World Project by Google in partnership with National Geographic Society and the World Resources Institute",
  },
  {
    name: "Elevation",
    detail: "NASA SRTM 30 m, used only in the cooling model.",
    license: "NASA/JPL public use terms (Farr et al., 2007)",
  },
  {
    name: "Hospitals and schools",
    detail: "Overture Maps places, via BigQuery public data.",
    license: "CDLA Permissive 2.0 and Apache 2.0, depending on the contributing source",
  },
  {
    name: "Intervention guidance",
    detail: "WRI India, Strengthening Climate Action and Resilience Planning for Bengaluru (2022), and US EPA, Reducing Urban Heat Islands: Compendium of Strategies (2014).",
    license: "Cited by page; see each recommendation",
  },
];

export function MethodPage() {
  const q = useResults();
  return (
    <div className={styles.page}>
      <article className={styles.article}>
        <h1 className={styles.h1}>How Penumbra works</h1>
        <p className={styles.lead}>
          Penumbra ranks every ward in Bengaluru by heat risk from satellite data, answers planning questions through a team of agents, and plans cooling work within a
          budget. The language model plans and writes. Every number comes from a database query or plain code, and is checked before you see it.
        </p>
        {q.isPending && <Loading step="Loading the results file." />}
        {q.isError && <ErrorState message={q.error.message} onRetry={() => q.refetch()} />}
        {q.data && <Body r={q.data} />}
      </article>
    </div>
  );
}

function Body({ r }: { r: Results }) {
  const cur = r.coverage.years.find((y) => y.year === CURRENT_YEAR);
  const base = r.coverage.years.find((y) => y.year === BASELINE_YEAR);
  const ndvi = r.cooling_model.effects.find((e) => e.usable);
  const unusable = r.cooling_model.effects.filter((e) => !e.usable);
  const rhos = r.weight_sensitivity.rows.map((x) => x.spearman_rho);
  const p = r.plan_comparison;
  const w = r.risk_weights;

  return (
    <>
      <section className={styles.section}>
        <h2 className={styles.h2}>What it measures</h2>
        <p>
          For each of the {cur?.wards ?? "city's"} wards, Penumbra measures surface temperature, green cover (NDVI) and built-up share from pre-monsoon satellite
          images, and combines them with population. Surface temperature is how hot the ground and roofs are, not the air a person feels, and the satellite passes in
          the morning rather than at peak afternoon heat.
        </p>
        {cur && base && (
          <p>
            Ward averages ranged from {celsius(cur.lst_min_c)} to {celsius(cur.lst_max_c)} in {CURRENT_YEAR} and from {celsius(base.lst_min_c)} to{" "}
            {celsius(base.lst_max_c)} in {BASELINE_YEAR}. Clouds hid little: every ward kept at least {percent(Math.min(cur.min_valid_pixel_frac, base.min_valid_pixel_frac), 1)} of
            its area in both years.
          </p>
        )}
        <p className={styles.caveat}>
          The city-wide average was warmer in {BASELINE_YEAR} ({base ? celsius(base.lst_avg_c) : "not available"}) than in {CURRENT_YEAR} ({cur ? celsius(cur.lst_avg_c) : "not available"}). Each
          year is a single March to May composite, so the difference may reflect that season's weather as much as any lasting change. Read "change since{" "}
          {BASELINE_YEAR}" as a comparison of two seasons, not a long-term trend.
        </p>
        <Source text={r.coverage.source} />
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Data sources</h2>
        <dl className={styles.sources}>
          {SOURCES.map((s) => (
            <div key={s.name}>
              <dt>{s.name}</dt>
              <dd>
                {s.detail} <span className={styles.license}>License: {s.license}.</span>
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>How the risk score works</h2>
        <p>
          Each ward gets four percentile ranks against every other ward: surface temperature, lack of green cover, built-up share, and population density. The heat risk
          score is their weighted sum, from 0 to 1. The default weights are {percent(w.heat)} temperature, {percent(w.green)} green deficit, {percent(w.built)} built-up
          and {percent(w.exposure)} people exposed. You can change them on the <Link to="/">map</Link>.
        </p>
        <p>
          The ranking barely moves when the weights move. Shifting any one weight by 10 points either way keeps the rank correlation with the default ranking between{" "}
          {Math.min(...rhos).toFixed(3)} and {Math.max(...rhos).toFixed(3)} (Spearman).
        </p>
        <table className={styles.table}>
          <caption>Rank correlation with the default ranking, {CURRENT_YEAR}</caption>
          <thead>
            <tr>
              <th scope="col">Weight changed</th>
              <th scope="col" className={styles.r}>
                Spearman
              </th>
            </tr>
          </thead>
          <tbody>
            {r.weight_sensitivity.rows.map((x) => (
              <tr key={x.perturbation}>
                <th scope="row">{x.perturbation.replace("+0.1", "up 10 points").replace("-0.1", "down 10 points")}</th>
                <td className={styles.r}>{x.spearman_rho.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Source text={r.weight_sensitivity.source} />
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Checking the ranking against the city</h2>
        <p>
          The coolest wards include ones around known lakes and old tree cover, such as Agaram (Agaram Lake), Sadashiva Nagara (next to Sankey Tank) and Sampangirama Nagar (near Cubbon
          Park). The hottest are dense, low-vegetation neighbourhoods in the old core. Several others have no landmark we could check either way. This is a qualitative
          check, not an overlay against a lake or park dataset.
        </p>
        <div className={styles.twoLists}>
          <Extremes title="Highest risk" rows={r.ranking_extremes.hottest} />
          <Extremes title="Lowest risk" rows={r.ranking_extremes.coolest} />
        </div>
        <Source text={r.ranking_extremes.source} />
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>The cooling model</h2>
        <p>
          To estimate what an intervention might do, Penumbra fits a ridge regression of surface temperature on green cover, built-up share, elevation and distance to
          water, over {people(r.cooling_model.n_samples)} points on a 150 m grid. It is tested with spatial block cross-validation, so neighbouring points never sit on both
          sides of a test.
        </p>
        <p>
          On held-out blocks it explains {percent(r.cooling_model.held_out_r2)} of the variation (R² {r.cooling_model.held_out_r2.toFixed(2)}), with a typical error of{" "}
          {celsius(r.cooling_model.held_out_rmse_c, 2)}. That is a weak to moderate fit: roofs, materials, waste heat and wind all matter and are not in the model. Every effect
          it gives is a modeled association, not a promise.
        </p>
        {ndvi && (
          <p>
            Raising green cover by {ndvi.unit_change} NDVI is associated with a change of {signedCelsius(ndvi.high_c, 2)} to {signedCelsius(ndvi.low_c, 2)} in surface temperature (90%
            bootstrap range). Tree canopy, lake and wetland buffers, and pocket parks are modeled through this term.
          </p>
        )}
        {unusable.length > 0 && (
          <p className={styles.caveat}>
            The built-up term is not used. Green cover and built-up share move together in this city, and the fitted model gave built-up share the opposite sign to its
            simple relationship with temperature. So cool roofs and permeable paving, which work through reflectance and permeability rather than vegetation, get no modeled
            cooling in Penumbra. They are shown with their published evidence instead.
          </p>
        )}
        <Source text={`${r.cooling_model.source}, ${r.cooling_model.model_type}, fitted ${r.cooling_model.fitted_date}`} />
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Budget planning</h2>
        <p>
          The planner is plain code with no language model. It funds the intervention with the most modeled cooling per rupee, weighted by the people in each ward, until
          the budget runs out, with a cap per ward. It then funds the same catalog from the hottest ward down, for comparison.
        </p>
        <p>
          For {p.corporation} corporation with {rupeesShort(p.budget_inr)}, the plan models {personC(p.optimized.total_person_c)} of cooling across{" "}
          {people(p.optimized.people_covered)} people in {p.optimized.wards_covered} wards. Funding the hottest wards first models {personC(p.naive.total_person_c)} across{" "}
          {people(p.naive.people_covered)} people in {p.naive.wards_covered} wards. Costs are assumed until sourced.
        </p>
        <Source text={p.source} />
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Evaluation</h2>
        {r.evaluation ? (
          <pre className={styles.pre}>{JSON.stringify(r.evaluation, null, 2)}</pre>
        ) : (
          <p>
            The comparison of Gemini alone, the agents without verification, and full Penumbra has not been run yet. Its results will appear here from the evaluation run,
            not typed by hand.
          </p>
        )}
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Limitations</h2>
        <ul className={styles.list}>
          <li>Surface temperature is not air temperature, and the satellite passes in the morning.</li>
          <li>Each year is one pre-monsoon season, so year-to-year change mixes weather with lasting change.</li>
          <li>Population is 2011 Census data apportioned to the 2025 ward boundaries.</li>
          <li>Cooling effects are modeled associations from a weak to moderate model, not guaranteed outcomes.</li>
          <li>Intervention costs are assumptions until replaced with real quotes.</li>
          <li>Penumbra makes no claims about individual streets, buildings or addresses.</li>
        </ul>
      </section>

      <p className={styles.generated}>
        Figures on this page come from {r.generated_by}, generated {dateTime(r.generated_at)}.
      </p>
    </>
  );
}

function Source({ text }: { text: string }) {
  return <p className={styles.source}>Source: {text}</p>;
}

function Extremes({ title, rows }: { title: string; rows: Results["ranking_extremes"]["hottest"] }) {
  return (
    <div>
      <h3 className={styles.h3}>{title}</h3>
      <ol className={styles.extremes}>
        {rows.map((x) => (
          <li key={x.ward_key}>
            <Link to={`/?ward=${encodeURIComponent(x.ward_key)}`}>{x.ward_name}</Link>
            <span className={styles.meta}>
              {x.corporation}, {celsius(x.lst_mean_c)}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
