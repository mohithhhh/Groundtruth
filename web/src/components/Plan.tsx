import type { AllocationItem, CatalogItem, PlanResponse } from "../lib/api";
import { people, personC, rupees, rupeesShort, signedCelsius } from "../lib/format";
import { FigureChip } from "./FigureChip";
import styles from "./Plan.module.css";

export function ComparisonBlock({ plan }: { plan: PlanResponse }) {
  const c = plan.comparison;
  const id = plan.tool_result_id;
  const max = Math.max(c.optimized_total_person_c, c.naive_total_person_c, 1);
  const maxPeople = Math.max(c.optimized_people_covered, c.naive_people_covered, 1);
  return (
    <section className={styles.compare} aria-labelledby="compare-title">
      <h2 id="compare-title" className={styles.h2}>
        This plan against funding the hottest wards first
      </h2>
      <p className={styles.lede}>
        Same budget, catalog and costs. The only difference is the order: this plan funds the most cooling per rupee anywhere in scope; the comparison funds wards
        from hottest down.
      </p>
      <div className={styles.metrics}>
        <Metric
          title="Modeled cooling"
          hint="Ward cooling times the people living there"
          a={{ value: c.optimized_total_person_c, text: personC(c.optimized_total_person_c), path: "data.comparison.optimized_total_person_c" }}
          b={{ value: c.naive_total_person_c, text: personC(c.naive_total_person_c), path: "data.comparison.naive_total_person_c" }}
          max={max}
          id={id}
        />
        <Metric
          title="People in funded wards"
          a={{ value: c.optimized_people_covered, text: people(c.optimized_people_covered), path: "data.comparison.optimized_people_covered" }}
          b={{ value: c.naive_people_covered, text: people(c.naive_people_covered), path: "data.comparison.naive_people_covered" }}
          max={maxPeople}
          id={id}
        />
      </div>
      <dl className={styles.small}>
        <div>
          <dt>Wards funded</dt>
          <dd>
            <FigureChip toolResultId={id} path="data.comparison.optimized_wards_covered" label="Wards funded by this plan">
              {String(c.optimized_wards_covered)}
            </FigureChip>{" "}
            against{" "}
            <FigureChip toolResultId={id} path="data.comparison.naive_wards_covered" label="Wards funded hottest-first">
              {String(c.naive_wards_covered)}
            </FigureChip>
          </dd>
        </div>
        <div>
          <dt>Spent</dt>
          <dd>
            <FigureChip toolResultId={id} path="data.comparison.optimized_cost_inr" label="Budget spent by this plan">
              {rupeesShort(c.optimized_cost_inr)}
            </FigureChip>{" "}
            against{" "}
            <FigureChip toolResultId={id} path="data.comparison.naive_cost_inr" label="Budget spent hottest-first">
              {rupeesShort(c.naive_cost_inr)}
            </FigureChip>
          </dd>
        </div>
      </dl>
    </section>
  );
}

function Metric(props: {
  title: string;
  hint?: string;
  a: { value: number; text: string; path: string };
  b: { value: number; text: string; path: string };
  max: number;
  id: string;
}) {
  const { title, hint, a, b, max, id } = props;
  return (
    <div className={styles.metric}>
      <p className={styles.mTitle}>
        {title}
        {hint && <span className={styles.mHint}>{hint}</span>}
      </p>
      <div className={styles.bars}>
        <span className={styles.who}>This plan</span>
        <span className={styles.barTrack}>
          <span className={styles.barPlan} style={{ width: `${(a.value / max) * 100}%` }} />
        </span>
        <FigureChip toolResultId={id} path={a.path} label={`${title}, this plan`}>
          {a.text}
        </FigureChip>
        <span className={styles.who}>Hottest first</span>
        <span className={styles.barTrack}>
          <span className={styles.barNaive} style={{ width: `${(b.value / max) * 100}%` }} />
        </span>
        <FigureChip toolResultId={id} path={b.path} label={`${title}, hottest wards first`}>
          {b.text}
        </FigureChip>
      </div>
    </div>
  );
}

export function AllocationTable({ plan, catalog, wardLabel }: { plan: PlanResponse; catalog: Map<string, CatalogItem>; wardLabel: (a: AllocationItem) => string }) {
  const id = plan.tool_result_id;
  if (plan.allocation.length === 0) {
    return <p className={styles.lede}>This budget does not cover one unit of any intervention with a modeled cooling effect. Raise the budget or lower a cost.</p>;
  }
  return (
    <section aria-labelledby="alloc-title">
      <h2 id="alloc-title" className={styles.h2}>
        Where the money goes
      </h2>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">Ward</th>
              <th scope="col">Intervention</th>
              <th scope="col" className={styles.r}>
                Amount
              </th>
              <th scope="col" className={styles.r}>
                Modeled cooling
              </th>
              <th scope="col" className={styles.r}>
                People
              </th>
            </tr>
          </thead>
          <tbody>
            {plan.allocation.map((a, i) => {
              const iv = catalog.get(a.intervention_id);
              const base = `data.allocation[${i}]`;
              return (
                <tr key={`${a.ward_key}-${a.intervention_id}`}>
                  <th scope="row" className={styles.ward}>
                    {wardLabel(a)}
                  </th>
                  <td>
                    {iv?.name ?? a.intervention_id}
                    <span className={styles.units}>
                      {a.units} × {iv?.unit.replace(/^1 /, "") ?? "unit"}
                    </span>
                  </td>
                  <td className={styles.r}>
                    <FigureChip toolResultId={id} path={`${base}.cost_inr`} label={`Amount for ${a.ward_name}`}>
                      {rupeesShort(a.cost_inr)}
                    </FigureChip>
                  </td>
                  <td className={styles.r}>
                    <FigureChip toolResultId={id} path={`${base}.cooling_high_c`} label={`Smaller end of modeled cooling, ${a.ward_name}`}>
                      {signedCelsius(a.cooling_high_c, 2)}
                    </FigureChip>
                    <span className={styles.to}> to </span>
                    <FigureChip toolResultId={id} path={`${base}.cooling_low_c`} label={`Larger end of modeled cooling, ${a.ward_name}`}>
                      {signedCelsius(a.cooling_low_c, 2)}
                    </FigureChip>
                  </td>
                  <td className={styles.r}>
                    <FigureChip toolResultId={id} path={`${base}.population`} label={`People in ${a.ward_name}`}>
                      {people(a.population)}
                    </FigureChip>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function CostInput({ item, value, onChange }: { item: CatalogItem; value: number; onChange: (v: number) => void }) {
  const changed = value !== item.cost_amount_inr_per_unit;
  return (
    <li className={styles.cost}>
      <div className={styles.costHead}>
        <label htmlFor={`cost-${item.intervention_id}`} className={styles.costName}>
          {item.name}
        </label>
        <span className={`${styles.tag} ${item.model_pathway_type === "modeled" ? styles.tagModeled : ""}`}>
          {item.model_pathway_type === "modeled" ? "Cooling modeled" : "Cooling not modeled"}
        </span>
      </div>
      <div className={styles.costRow}>
        <span className={styles.costPrefix}>Assumed cost ₹</span>
        <input
          id={`cost-${item.intervention_id}`}
          className="input"
          type="number"
          inputMode="numeric"
          min={1}
          step={1}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
        />
        <span className={styles.costUnit}>per {item.unit.replace(/^1 /, "")}</span>
      </div>
      {changed && <p className={styles.changed}>Default {rupees(item.cost_amount_inr_per_unit)}</p>}
    </li>
  );
}
