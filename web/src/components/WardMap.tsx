import { type ExpressionSpecification, type GeoJSONSource, type MapLayerMouseEvent, MapLibreMap, NavigationControl } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useMemo, useRef, useState } from "react";
import type { CorpGeoJSON, WardGeoJSON } from "../lib/data";
import type { Lang } from "../lib/prefs";
import { cssVar } from "../lib/views";
import styles from "./WardMap.module.css";

export interface Sweep {
  /** Increment to play the shade sweep once. */
  id: number;
  /** ward_key -> modeled class index after the plan. */
  targets: Map<string, number>;
}

interface Props {
  shapes: WardGeoJSON;
  corporations?: CorpGeoJSON;
  /** ward_key -> 1-based class index for the current view. */
  bins: Map<string, number>;
  ramp: string[];
  theme: string;
  lang: Lang;
  selectedKey?: string | null;
  highlightKeys?: string[];
  sweep?: Sweep | null;
  onSelect?: (wardKey: string) => void;
  tooltip?: (wardKey: string) => { title: string; value: string } | null;
  ariaLabel: string;
}

const SWEEP_MS = 900;
const LABEL_MIN_ZOOM = 12.2;

function reducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

function fillExpression(ramp: string[]): ExpressionSpecification {
  const stops: (number | string)[] = [];
  ramp.forEach((name, i) => stops.push(i + 1, cssVar(name)));
  return [
    "case",
    ["<", ["to-number", ["feature-state", "bin"], 0], 1],
    cssVar("--no-data"),
    ["interpolate", ["linear"], ["to-number", ["feature-state", "bin"], 0], ...stops],
  ] as ExpressionSpecification;
}

function bbox(fc: WardGeoJSON): [[number, number], [number, number]] {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const visit = (c: unknown): void => {
    if (typeof (c as number[])[0] === "number") {
      const [x, y] = c as number[];
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    } else (c as unknown[]).forEach(visit);
  };
  fc.features.forEach((f) => visit(f.geometry.coordinates));
  return [[minX, minY], [maxX, maxY]];
}

interface Label {
  key: string;
  x: number;
  y: number;
  text: string;
}

export function WardMap(props: Props) {
  const { shapes, corporations, bins, ramp, theme, lang, selectedKey, highlightKeys, sweep, onSelect, tooltip, ariaLabel } = props;
  const containerRef = useRef<HTMLDivElement>(null);
  const bandRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [ready, setReady] = useState(false);
  const [labels, setLabels] = useState<Label[]>([]);
  const [hover, setHover] = useState<{ key: string; x: number; y: number } | null>(null);
  const appliedSweep = useRef<Sweep | null>(null);
  const prev = useRef({ selected: null as string | null, highlight: [] as string[], hover: null as string | null });

  const callbacks = useRef({ onSelect, lang });
  callbacks.current = { onSelect, lang };

  const bounds = useMemo(() => bbox(shapes), [shapes]);
  const byKey = useMemo(() => new Map(shapes.features.map((f) => [f.properties.ward_key, f.properties])), [shapes]);

  // Create the map once.
  useEffect(() => {
    if (!containerRef.current) return;
    const map = new MapLibreMap({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {},
        layers: [{ id: "bg", type: "background", paint: { "background-color": cssVar("--bg") } }],
      },
      bounds,
      fitBoundsOptions: {
        padding: window.innerWidth > 760 ? { top: 72, bottom: 24, left: 180, right: 48 } : { top: 56, bottom: 12, left: 12, right: 12 },
      },
      maxBounds: [
        [bounds[0][0] - 0.35, bounds[0][1] - 0.3],
        [bounds[1][0] + 0.35, bounds[1][1] + 0.3],
      ],
      minZoom: 9,
      maxZoom: 16,
      dragRotate: false,
      pitchWithRotate: false,
      touchPitch: false,
      attributionControl: { compact: true, customAttribution: "Ward boundaries: OpenCity (GBA, 2025). Satellite data: USGS Landsat, Google Dynamic World." },
    });
    map.touchZoomRotate.disableRotation();
    // Top-left, under the view switch: the ward sheet and source drawer
    // float over the right side. Hidden on phones, where pinch zoom is native.
    map.addControl(new NavigationControl({ showCompass: false }), "top-left");
    mapRef.current = map;

    map.on("load", () => {
      map.addSource("wards", { type: "geojson", data: shapes, promoteId: "ward_key" });
      if (corporations) map.addSource("corps", { type: "geojson", data: corporations });

      map.addLayer({ id: "ward-fill", type: "fill", source: "wards", paint: { "fill-color": fillExpression(ramp), "fill-opacity": 0.9 } });
      map.addLayer({ id: "ward-line", type: "line", source: "wards", paint: { "line-color": cssVar("--ward-stroke"), "line-width": 0.75 } });
      if (corporations)
        map.addLayer({ id: "corp-line", type: "line", source: "corps", paint: { "line-color": cssVar("--corp-stroke"), "line-width": 1.5, "line-opacity": 0.85 } });
      map.addLayer({
        id: "plan-line",
        type: "line",
        source: "wards",
        paint: { "line-color": cssVar("--accent"), "line-width": 2, "line-opacity": ["to-number", ["feature-state", "plan"], 0] },
      });
      map.addLayer({
        id: "highlight-line",
        type: "line",
        source: "wards",
        paint: { "line-color": cssVar("--link"), "line-width": 2.5, "line-opacity": ["case", ["boolean", ["feature-state", "highlight"], false], 1, 0] },
      });
      map.addLayer({
        id: "hover-line",
        type: "line",
        source: "wards",
        paint: { "line-color": cssVar("--link"), "line-width": 2, "line-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 1, 0] },
      });
      map.addLayer({
        id: "selected-glow",
        type: "line",
        source: "wards",
        paint: {
          "line-color": cssVar("--text"),
          "line-width": 8,
          "line-blur": 6,
          "line-opacity": ["case", ["boolean", ["feature-state", "selected"], false], 0.28, 0],
        },
      });
      map.addLayer({
        id: "selected-line",
        type: "line",
        source: "wards",
        paint: { "line-color": cssVar("--text"), "line-width": 2.5, "line-opacity": ["case", ["boolean", ["feature-state", "selected"], false], 1, 0] },
      });

      map.on("mousemove", "ward-fill", (e: MapLayerMouseEvent) => {
        const key = e.features?.[0]?.id as string | undefined;
        if (!key) return;
        map.getCanvas().style.cursor = "pointer";
        if (prev.current.hover !== key) {
          if (prev.current.hover) map.setFeatureState({ source: "wards", id: prev.current.hover }, { hover: false });
          map.setFeatureState({ source: "wards", id: key }, { hover: true });
          prev.current.hover = key;
        }
        setHover({ key, x: e.point.x, y: e.point.y });
      });
      map.on("mouseleave", "ward-fill", () => {
        map.getCanvas().style.cursor = "";
        if (prev.current.hover) map.setFeatureState({ source: "wards", id: prev.current.hover }, { hover: false });
        prev.current.hover = null;
        setHover(null);
      });
      map.on("click", "ward-fill", (e: MapLayerMouseEvent) => {
        const key = e.features?.[0]?.id as string | undefined;
        if (key) callbacks.current.onSelect?.(key);
      });
      setReady(true);
    });

    const ro = new ResizeObserver(() => map.resize());
    ro.observe(containerRef.current);
    return () => {
      ro.disconnect();
      map.remove();
      mapRef.current = null;
    };
    // The map is created once per shapes object; other props update below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shapes]);

  // Keep the source data current if shapes change identity (rare).
  useEffect(() => {
    const src = mapRef.current?.getSource("wards") as GeoJSONSource | undefined;
    if (ready && src) src.setData(shapes);
  }, [ready, shapes]);

  // Colours follow the theme and the active view's ramp.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    map.setPaintProperty("bg", "background-color", cssVar("--bg"));
    map.setPaintProperty("ward-fill", "fill-color", fillExpression(ramp));
    map.setPaintProperty("ward-line", "line-color", cssVar("--ward-stroke"));
    if (map.getLayer("corp-line")) map.setPaintProperty("corp-line", "line-color", cssVar("--corp-stroke"));
    map.setPaintProperty("plan-line", "line-color", cssVar("--accent"));
    map.setPaintProperty("highlight-line", "line-color", cssVar("--link"));
    map.setPaintProperty("hover-line", "line-color", cssVar("--link"));
    map.setPaintProperty("selected-glow", "line-color", cssVar("--text"));
    map.setPaintProperty("selected-line", "line-color", cssVar("--text"));
  }, [ready, ramp, theme]);

  // Base classes for the current view, plus any plan already applied.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    for (const f of shapes.features) {
      const key = f.properties.ward_key;
      map.setFeatureState({ source: "wards", id: key }, { bin: bins.get(key) ?? 0, plan: 0 });
    }
    const applied = appliedSweep.current;
    if (applied && sweep && applied.id === sweep.id) {
      for (const [key, to] of applied.targets) map.setFeatureState({ source: "wards", id: key }, { bin: to, plan: 1 });
    }
  }, [ready, bins, shapes, sweep]);

  // The shade sweep: a soft diagonal band crosses the city once; each
  // planned ward eases from its current class toward its modeled class as
  // the band passes it, and its outline turns canopy green.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !sweep || appliedSweep.current?.id === sweep.id) return;

    const finish = () => {
      for (const [key, to] of sweep.targets) map.setFeatureState({ source: "wards", id: key }, { bin: to, plan: 1 });
      appliedSweep.current = sweep;
      if (bandRef.current) bandRef.current.style.opacity = "0";
    };
    if (reducedMotion()) {
      finish();
      return;
    }

    const canvas = map.getCanvas();
    const w = canvas.clientWidth || 1;
    const h = canvas.clientHeight || 1;
    const targets = [...sweep.targets].map(([key, to]) => {
      const p = byKey.get(key);
      const pt = p ? map.project(p.centroid as [number, number]) : { x: 0, y: 0 };
      return { key, from: bins.get(key) ?? 0, to, d: (pt.x / w + pt.y / h) / 2 };
    });

    let raf = 0;
    const start = performance.now();
    const band = bandRef.current;
    const ease = (t: number) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);
    const frame = (now: number) => {
      const p = Math.min(1, (now - start) / SWEEP_MS);
      const pos = -0.3 + 1.6 * p;
      if (band) {
        const c = pos * 100;
        band.style.opacity = "1";
        band.style.background = `linear-gradient(135deg, transparent ${c - 24}%, rgba(23,48,44,0.10) ${c - 11}%, rgba(23,48,44,0.34) ${c}%, rgba(23,48,44,0.10) ${c + 11}%, transparent ${c + 24}%)`;
      }
      for (const t of targets) {
        const k = ease(Math.max(0, Math.min(1, (pos - t.d) / 0.22)));
        map.setFeatureState({ source: "wards", id: t.key }, { bin: t.from + (t.to - t.from) * k, plan: k });
      }
      if (p < 1) raf = requestAnimationFrame(frame);
      else finish();
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [ready, sweep, bins, byKey]);

  // Selection and highlights.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    if (prev.current.selected) map.setFeatureState({ source: "wards", id: prev.current.selected }, { selected: false });
    if (selectedKey) {
      map.setFeatureState({ source: "wards", id: selectedKey }, { selected: true });
      const p = byKey.get(selectedKey);
      if (p) {
        const pt = map.project(p.centroid as [number, number]);
        const W = map.getCanvas().clientWidth;
        const wide = W > 760;
        // The sheet covers roughly the right 460px on wide screens.
        const hidden = wide ? pt.x > W - 470 || pt.x < 40 : !map.getBounds().contains(p.centroid as [number, number]);
        if (hidden) {
          map.easeTo({ center: p.centroid as [number, number], offset: wide ? [-230, 0] : [0, -80], duration: reducedMotion() ? 0 : 400 });
        }
      }
    }
    prev.current.selected = selectedKey ?? null;
  }, [ready, selectedKey, byKey]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    for (const k of prev.current.highlight) map.setFeatureState({ source: "wards", id: k }, { highlight: false });
    const keys = highlightKeys ?? [];
    for (const k of keys) map.setFeatureState({ source: "wards", id: k }, { highlight: true });
    prev.current.highlight = keys;
    if (keys.length) {
      const pts = keys.map((k) => byKey.get(k)?.centroid).filter(Boolean) as [number, number][];
      if (pts.length) {
        const xs = pts.map((p) => p[0]);
        const ys = pts.map((p) => p[1]);
        const pad = 0.02;
        map.fitBounds(
          [
            [Math.min(...xs) - pad, Math.min(...ys) - pad],
            [Math.max(...xs) + pad, Math.max(...ys) + pad],
          ],
          {
            padding: map.getCanvas().clientWidth > 760 ? { top: 64, bottom: 48, left: 290, right: 64 } : 40,
            maxZoom: 13,
            duration: reducedMotion() ? 0 : 600,
          },
        );
      }
    }
  }, [ready, highlightKeys, byKey]);

  // Ward labels as HTML, only at zooms where a label fits inside its ward.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    let raf = 0;
    const update = () => {
      raf = 0;
      if (map.getZoom() < LABEL_MIN_ZOOM) {
        setLabels((l) => (l.length ? [] : l));
        return;
      }
      const canvas = map.getCanvas();
      const W = canvas.clientWidth;
      const H = canvas.clientHeight;
      const center = map.getCenter();
      const a = map.project([center.lng, center.lat]);
      const b = map.project([center.lng + 0.01, center.lat]);
      const pxPerKm = Math.hypot(b.x - a.x, b.y - a.y) / (0.01 * 111.32 * Math.cos((center.lat * Math.PI) / 180));
      const placed: { x0: number; y0: number; x1: number; y1: number }[] = [];
      const out: Label[] = [];
      const sorted = [...shapes.features].sort((f, g) => g.properties.area_km2 - f.properties.area_km2);
      for (const f of sorted) {
        const p = f.properties;
        const text = callbacks.current.lang === "kn" && p.ward_name_kn ? p.ward_name_kn : p.ward_name;
        const side = Math.sqrt(p.area_km2) * pxPerKm;
        const width = text.length * 6.6 + 8;
        if (side < width * 0.9) continue;
        const pt = map.project(p.centroid as [number, number]);
        if (pt.x < 0 || pt.y < 0 || pt.x > W || pt.y > H) continue;
        const box = { x0: pt.x - width / 2, y0: pt.y - 9, x1: pt.x + width / 2, y1: pt.y + 9 };
        if (placed.some((q) => box.x0 < q.x1 && box.x1 > q.x0 && box.y0 < q.y1 && box.y1 > q.y0)) continue;
        placed.push(box);
        out.push({ key: p.ward_key, x: pt.x, y: pt.y, text });
        if (out.length >= 80) break;
      }
      setLabels(out);
    };
    const schedule = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    map.on("move", schedule);
    map.on("resize", schedule);
    schedule();
    return () => {
      map.off("move", schedule);
      map.off("resize", schedule);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [ready, shapes, lang]);

  const tip = hover && tooltip ? tooltip(hover.key) : null;

  return (
    <div className={styles.wrap}>
      <div ref={containerRef} className={styles.map} role="region" aria-label={ariaLabel} />
      <div ref={bandRef} className={styles.band} aria-hidden="true" />
      <div className={styles.labels} aria-hidden="true">
        {labels.map((l) => (
          <span key={l.key} className={`${styles.label} ${lang === "kn" ? "kn" : ""}`} style={{ transform: `translate(${l.x}px, ${l.y}px)` }}>
            {l.text}
          </span>
        ))}
      </div>
      {tip && hover && (
        <div className={styles.tooltip} style={{ transform: `translate(${hover.x + 14}px, ${hover.y + 14}px)` }} aria-hidden="true">
          <span className={`${styles.tipTitle} ${lang === "kn" ? "kn" : ""}`}>{tip.title}</span>
          <span className={styles.tipValue}>{tip.value}</span>
        </div>
      )}
    </div>
  );
}
