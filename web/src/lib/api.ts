// Typed client for the Groundtruth FastAPI server. Shapes mirror server/api/*.py.

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "Groundtruth could not reach its server. Check your connection and try again.");
  }
  if (!res.ok) {
    let detail = `The server returned ${res.status}.`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export type Corporation = "Central" | "East" | "North" | "South" | "West";
export const CORPORATIONS: Corporation[] = ["Central", "East", "North", "South", "West"];

export interface WardRow {
  ward_key: string;
  ward_name: string;
  ward_name_kn: string;
  corporation: Corporation;
  lst_mean_c: number;
  ndvi_mean: number;
  built_frac: number;
  composite_risk: number;
  rank: number;
  delta_lst_c: number;
}

export interface RiskRow {
  ward_key: string;
  ward_name: string;
  ward_name_kn: string;
  corporation: Corporation;
  composite_risk: number;
  rank: number;
  delta_lst_c: number;
}

export interface Weights {
  heat: number;
  green: number;
  built: number;
  exposure: number;
}

export interface WardMetrics {
  ward_key: string;
  ward_no: number;
  ward_name: string;
  ward_name_kn: string;
  corporation: Corporation;
  ac: string;
  area_km2: number;
  lst_mean_c: number;
  lst_max_c: number;
  ndvi_mean: number;
  built_frac: number;
  valid_pixel_frac: number;
  population: number;
  population_source_year: number;
  composite_risk: number;
  rank: number;
  delta_lst_c: number;
}

export interface Citation {
  doc_id: string;
  page: number;
  quote: string;
}

export interface Recommendation {
  intervention_id: string;
  name: string;
  unit: string;
  cost_inr_per_unit: number;
  cost_is_assumption: boolean;
  cost_note: string;
  citations: Citation[];
  effect_low_c: number | null;
  effect_mid_c: number | null;
  effect_high_c: number | null;
  effect_type: "modeled_association" | "not_quantified";
  cited_fact?: string | null;
}

export interface GuidanceDocument {
  doc_id: string;
  title: string;
  publisher: string;
  url: string;
  doc_date: string;
}

export interface YearChange {
  ward_key: string;
  ward_name: string;
  value_a: number;
  value_b: number;
  change: number;
}

export interface SourceSummary {
  tool_result_id: string;
  tool_name: string;
  description: string;
  created_at: string;
}

export interface Brief {
  labels: Record<string, string>;
  lang: "en" | "kn";
  unverified_translation: boolean;
  year: number;
  baseline_year: number;
  season: string;
  ward: WardMetrics;
  baseline: WardMetrics | null;
  city_median: { ward_key: string; lst_mean_c: number; city_median_lst_c: number; difference_c: number } | null;
  recommended_actions: Recommendation[];
  facilities: { counts: { hospital: number; school: number }; facilities: { type: string; name: string; category: string }[] };
  changes: { ndvi_mean: YearChange | null; built_frac: YearChange | null };
  guidance_documents: GuidanceDocument[];
  limitations: string[];
  generated_at: string;
  tool_result_ids: Record<"ward" | "baseline" | "city_median" | "interventions" | "facilities" | "green_change" | "built_change", string>;
  sources: SourceSummary[];
}

export interface Claim {
  id: string;
  text: string;
  kind: "entity" | "number";
  value?: number | null;
  unit?: string | null;
  tool_result_id: string;
  path: string;
}

export interface TraceStep {
  step: number;
  description: string;
  duration_s: number;
}

export interface AskResponse {
  narrative: string;
  narrative_template: string;
  claims: Claim[];
  verification: { verified: number; total: number; removed: { id: string | null; reason: string }[] };
  highlight_ward_keys: string[];
  trace: TraceStep[];
  session_id: string;
}

export interface Source {
  tool_name: string;
  description: string;
  params: Record<string, unknown>;
  data: unknown;
  created_at: string;
}

export interface CatalogItem {
  intervention_id: string;
  name: string;
  unit: string;
  model_pathway_type: "modeled" | "not_modeled";
  model_pathway_description: string;
  cost_amount_inr_per_unit: number;
  cost_is_assumption: boolean;
  cost_note: string;
  cited_fact_text: string | null;
  citations: Citation[];
}

export interface AllocationItem {
  ward_key: string;
  ward_name: string;
  population: number;
  intervention_id: string;
  units: number;
  cost_inr: number;
  person_c: number;
  cooling_low_c: number;
  cooling_mid_c: number;
  cooling_high_c: number;
}

export interface PlanResponse {
  allocation: AllocationItem[];
  naive: AllocationItem[];
  comparison: {
    optimized_total_person_c: number;
    naive_total_person_c: number;
    optimized_people_covered: number;
    naive_people_covered: number;
    optimized_wards_covered: number;
    naive_wards_covered: number;
    optimized_cost_inr: number;
    naive_cost_inr: number;
  };
  assumptions: string[];
  tool_result_id: string;
  options_tool_result_id: string;
}

export const api = {
  wards: (year: number) => request<WardRow[]>(`/api/wards?year=${year}`),
  risk: (year: number, w: Weights) =>
    request<RiskRow[]>(
      `/api/risk?year=${year}&w_heat=${w.heat}&w_green=${w.green}&w_built=${w.built}&w_exposure=${w.exposure}`,
    ),
  brief: (wardKey: string, lang: "en" | "kn") =>
    request<Brief>(`/api/brief/${encodeURIComponent(wardKey)}?lang=${lang}`),
  ask: (question: string, sessionId?: string) =>
    request<AskResponse>("/api/ask", {
      method: "POST",
      body: JSON.stringify({ question, city_id: "bengaluru", session_id: sessionId }),
    }),
  source: (id: string) => request<Source>(`/api/sources/${encodeURIComponent(id)}`),
  interventions: () => request<CatalogItem[]>("/api/interventions"),
  plan: (budgetInr: number, corporation: Corporation | null, costOverrides: Record<string, number>) =>
    request<PlanResponse>("/api/plan", {
      method: "POST",
      body: JSON.stringify({ budget_inr: budgetInr, corporation, cost_overrides: costOverrides }),
    }),
};
