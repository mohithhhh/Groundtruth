import type { WardRow } from "./api";
import { type Classification, divergingClassification, quantileClassification } from "./bins";
import { celsius, ndvi, score, signedCelsius } from "./format";

export type ViewId = "risk" | "lst" | "change" | "green";

export interface MapView {
  id: ViewId;
  label: string;
  legendTitle: string;
  /** Shown under the legend: what the colour does and does not mean. */
  note: string;
  ramp: string[]; // CSS custom property names, light to dark
  value: (w: WardRow) => number;
  format: (v: number) => string;
  classify: (values: number[]) => Classification;
  methodLabel: (wardCount: number) => string;
  higherIsWorse: boolean;
}

const HEAT = ["--heat-1", "--heat-2", "--heat-3", "--heat-4", "--heat-5", "--heat-6", "--heat-7"];
const GREEN = ["--green-1", "--green-2", "--green-3", "--green-4", "--green-5", "--green-6", "--green-7"];
const CHANGE = ["--change-1", "--change-2", "--change-3", "--change-4", "--change-5"];

// Change classes: within ±0.5 °C reads as no clear change; beyond ±2 °C is strong.
const CHANGE_INNER = 0.5;
const CHANGE_OUTER = 2;

const quantileLabel = (n: number) => `Quantile bins, about ${Math.round(n / 7)} wards each`;

export function mapViews(baselineYear: number): Record<ViewId, MapView> {
  return {
    risk: {
      id: "risk",
      label: "Heat risk",
      legendTitle: "Heat risk score",
      note: "Combines surface temperature, green cover, built-up share and population density. Higher means act sooner.",
      ramp: HEAT,
      value: (w) => w.composite_risk,
      format: score,
      classify: (v) => quantileClassification(v, 7),
      methodLabel: quantileLabel,
      higherIsWorse: true,
    },
    lst: {
      id: "lst",
      label: "Surface temperature",
      legendTitle: "Surface temperature",
      note: "Surface temperature, not air temperature.",
      ramp: HEAT,
      value: (w) => w.lst_mean_c,
      format: (v) => celsius(v),
      classify: (v) => quantileClassification(v, 7),
      methodLabel: quantileLabel,
      higherIsWorse: true,
    },
    change: {
      id: "change",
      label: `Change since ${baselineYear}`,
      legendTitle: `Surface temperature change since ${baselineYear}`,
      note: "Each year is one pre-monsoon composite, so this compares two seasons, not a long-term trend.",
      ramp: CHANGE,
      value: (w) => w.delta_lst_c,
      format: (v) => signedCelsius(v),
      classify: (v) => divergingClassification(v, CHANGE_INNER, CHANGE_OUTER),
      methodLabel: () => `Fixed breaks at ±${CHANGE_INNER} and ±${CHANGE_OUTER} °C, centred on zero`,
      higherIsWorse: true,
    },
    green: {
      id: "green",
      label: "Green cover",
      legendTitle: "Green cover (NDVI)",
      note: "Vegetation index: near zero for bare or built ground, higher for denser green cover.",
      ramp: GREEN,
      value: (w) => w.ndvi_mean,
      format: ndvi,
      classify: (v) => quantileClassification(v, 7),
      methodLabel: quantileLabel,
      higherIsWorse: false,
    },
  };
}

export const VIEW_ORDER: ViewId[] = ["risk", "lst", "change", "green"];

export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
