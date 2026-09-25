import { useQuery } from "@tanstack/react-query";
import type { Weights } from "./api";

// Shape of web/public/data/results.json, written by pipeline/10_export_results.py.
export interface Results {
  generated_at: string;
  generated_by: string;
  coverage: {
    source: string;
    years: { year: number; wards: number; lst_min_c: number; lst_avg_c: number; lst_max_c: number; min_valid_pixel_frac: number }[];
  };
  risk_weights: Weights & { source: string };
  cooling_model: {
    source: string;
    held_out_r2: number;
    held_out_rmse_c: number;
    n_samples: number;
    model_type: string;
    fitted_date: string;
    effects: { intervention: string; unit_change: number; low_c: number; mid_c: number; high_c: number; usable: boolean; note: string }[];
  };
  weight_sensitivity: { source: string; rows: { perturbation: string; spearman_rho: number }[] };
  ranking_extremes: {
    source: string;
    hottest: { rank: number; ward_key: string; ward_name: string; corporation: string; lst_mean_c: number; ndvi_mean: number; composite_risk: number }[];
    coolest: { rank: number; ward_key: string; ward_name: string; corporation: string; lst_mean_c: number; ndvi_mean: number; composite_risk: number }[];
  };
  plan_comparison: {
    source: string;
    corporation: string;
    budget_inr: number;
    optimized: { total_person_c: number; people_covered: number; wards_covered: number; total_cost_inr: number };
    naive: { total_person_c: number; people_covered: number; wards_covered: number; total_cost_inr: number };
  };
  evaluation: null | Evaluation;
}

export type EvalConfig = "gemini_alone" | "agents_unverified" | "groundtruth";

export interface EvalSummary {
  questions: number;
  fully_correct: number;
  facts_correct: number;
  facts_expected: number;
  answers_with_unsupported_figures: number;
  unsupported_figures: number;
  errors: number;
  latency_median_s: number;
  latency_max_s: number;
  cost_usd_mean: number;
}

export interface Evaluation {
  source: string;
  generated_at: string;
  summary: Record<EvalConfig, EvalSummary>;
  verifier: { claims: number; verified: number };
  questions: ({ id: string; category: string; question: string } & Record<EvalConfig, { correct: boolean; unsupported: number }>)[];
}

export function useResults() {
  return useQuery({
    queryKey: ["results"],
    queryFn: async (): Promise<Results> => {
      const res = await fetch("/data/results.json");
      if (!res.ok) throw new Error(`Could not load the results file (${res.status}).`);
      return res.json();
    },
    staleTime: Infinity,
  });
}

export function defaultWeights(r: Results | undefined): Weights | null {
  if (!r) return null;
  const { heat, green, built, exposure } = r.risk_weights;
  return { heat, green, built, exposure };
}
