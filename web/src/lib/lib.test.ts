import { describe, expect, it } from "vitest";
import { rebalance } from "../components/WeightSliders";
import { classify, classRange, divergingClassification, quantileClassification } from "./bins";
import { signedCelsius } from "./format";
import { splitTemplate } from "./narrative";
import { normalizePath, resolvePath } from "./path";

describe("quantile classification", () => {
  const values = Array.from({ length: 70 }, (_, i) => i);
  const c = quantileClassification(values, 7);

  it("puts roughly equal counts in each class", () => {
    const counts = new Array(7).fill(0);
    values.forEach((v) => counts[classify(v, c) - 1]++);
    counts.forEach((n) => expect(n).toBeGreaterThanOrEqual(9));
  });

  it("keeps the extremes in the first and last class", () => {
    expect(classify(0, c)).toBe(1);
    expect(classify(69, c)).toBe(7);
  });

  it("gives legend ranges that start at the minimum and end at the maximum", () => {
    expect(classRange(1, c)[0]).toBe(0);
    expect(classRange(7, c)[1]).toBe(69);
  });
});

describe("diverging classification", () => {
  const c = divergingClassification([-3, 0, 3], 0.5, 2);
  it("centres zero in the middle class", () => {
    expect(classify(0, c)).toBe(3);
    expect(classify(0.4, c)).toBe(3);
    expect(classify(-0.6, c)).toBe(2);
    expect(classify(-2.5, c)).toBe(1);
    expect(classify(2.5, c)).toBe(5);
  });
});

describe("path resolution mirrors the server verifier", () => {
  const entry = { tool_name: "rank_wards", data: [{ ward_name: "Varthur", value: 1.02 }] };
  it("resolves indexed paths", () => {
    expect(resolvePath(entry, "data[0].ward_name")).toBe("Varthur");
  });
  it("strips Gemini's function-response prefix", () => {
    expect(resolvePath(entry, normalizePath("rank_wards", "rank_wards_response.data[0].value"))).toBe(1.02);
  });
  it("returns undefined for a missing field instead of throwing", () => {
    expect(resolvePath(entry, "data[3].ward_name")).toBeUndefined();
  });
});

describe("narrative templates", () => {
  it("splits text and claim tokens in order", () => {
    expect(splitTemplate("Ward {c1} warmed by {c2}°C.")).toEqual([
      { kind: "text", text: "Ward " },
      { kind: "claim", id: "c1" },
      { kind: "text", text: " warmed by " },
      { kind: "claim", id: "c2" },
      { kind: "text", text: "°C." },
    ]);
  });
});

describe("weight rebalancing", () => {
  const w = { heat: 0.4, green: 0.2, built: 0.15, exposure: 0.25 };
  it("keeps the four weights summing to one", () => {
    const next = rebalance(w, "heat", 0.7);
    const sum = next.heat + next.green + next.built + next.exposure;
    expect(sum).toBeCloseTo(1, 10);
    expect(next.heat).toBeCloseTo(0.7);
  });
  it("keeps the other weights in proportion", () => {
    const next = rebalance(w, "heat", 0.5);
    expect(next.green / next.built).toBeCloseTo(0.2 / 0.15);
  });
});

describe("formatting", () => {
  it("uses a true minus sign and never shows negative zero", () => {
    expect(signedCelsius(-1.234)).toBe("−1.2 °C");
    expect(signedCelsius(-0.01)).toBe("0.0 °C");
  });
});
