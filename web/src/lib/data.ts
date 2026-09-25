import { useQuery } from "@tanstack/react-query";
import { api, type WardRow } from "./api";

export interface WardFeatureProps {
  ward_key: string;
  ward_no: number;
  ward_name: string;
  ward_name_kn: string;
  corporation: string;
  centroid: [number, number];
  area_km2: number;
}

export type WardGeoJSON = GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.MultiPolygon, WardFeatureProps>;
export type CorpGeoJSON = GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.MultiPolygon, { corporation: string }>;

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Could not load ${url} (${res.status}).`);
  return res.json();
}

export function useWardShapes() {
  return useQuery({
    queryKey: ["geo", "wards"],
    queryFn: () => getJson<WardGeoJSON>("/data/wards.geojson"),
    staleTime: Infinity,
  });
}

export function useCorporationShapes() {
  return useQuery({
    queryKey: ["geo", "corporations"],
    queryFn: () => getJson<CorpGeoJSON>("/data/corporations.geojson"),
    staleTime: Infinity,
  });
}

export function useWards(year: number) {
  return useQuery({
    queryKey: ["wards", year],
    queryFn: () => api.wards(year),
    staleTime: 10 * 60_000,
  });
}

export function byKey<T extends { ward_key: string }>(rows: T[] | undefined): Map<string, T> {
  return new Map((rows ?? []).map((r) => [r.ward_key, r]));
}

export type { WardRow };
