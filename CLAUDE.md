# Groundtruth: Build Brief for Claude Code

Save this file as `CLAUDE.md` in the repository root. Claude Code reads it as project instructions. Then start a session with the kickoff message in Section 0.

---

## 0. Kickoff message (paste this into Claude Code)

> Read CLAUDE.md fully. Then read plan.md and README.md. Summarize back to me, in under 15 lines, what you are building, the phase order, and the first three things you will do. Do not write code until I confirm. After I confirm, work phase by phase, stop at each phase's exit test, show me the evidence, and wait for my go-ahead before the next phase.

---

## Current state of the repo (as of 25 Sep 2026)

Phases 1 to 6 are built and deployed. Check `docs/NOTES.md` for the running
log and `docs/DECISIONS.md` for every deviation from this brief.

- Live: `https://groundtruth-app-891315005311.us-central1.run.app` (Cloud Run
  service `groundtruth-app`, one container: FastAPI serves `/api` and the
  built web app; runs as the pre-existing `penumbra-app` service account,
  which was not renamed). The original service `penumbra-app` still exists
  at `https://penumbra-app-891315005311.us-central1.run.app`, scaled to
  min-instances=0.
- `pipeline/` data layer (01-10), `model/` cooling model, `cities/bengaluru.yaml`
  intervention catalog, `server/` API + ADK agent + verifier + optimizer,
  `web/` React app.
- Commands:
  - Backend: `source .venv/bin/activate && GOOGLE_GENAI_USE_ENTERPRISE=1 GOOGLE_CLOUD_PROJECT=penumbra-509416 GOOGLE_CLOUD_LOCATION=us-central1 MODEL_ID=gemini-2.5-flash BQ_DATASET=penumbra uvicorn server.main:app --port 8080`
  - Web dev: `cd web && npm run dev` (proxies `/api` to :8080; set `API_TARGET` to use the deployed API)
  - Eval: `python eval/run_eval.py` (same env vars as the backend; about 10 minutes, a few US cents), then `python pipeline/10_export_results.py` to refresh the Method page
  - Tests: `python -m pytest server/tests eval` and `cd web && npm test`; one test: `python -m pytest server/tests/test_verify.py::test_pass_entity_and_number`
  - Build: `cd web && npm run build` (typechecks, then bundles to `web/dist`)
  - Deploy: the `gcloud run deploy` command in Section 11, with `GOOGLE_GENAI_USE_ENTERPRISE=1` added (the ADK variable; `GOOGLE_GENAI_USE_VERTEXAI` is deprecated)
- Smoke test a deployment: `python scripts/smoke.py <url>`. Video script and deck outline: `docs/pitch.md`. Architecture: `docs/architecture.md`.
- Cloud Run runs with `--min-instances=1` for judging; set it back to 0 afterwards. Keep `--min-instances=1` in any redeploy until then.
- Open for the team: manual-timing comparison (not measured), LICENSE choice, team names and video/deck links in README, making the repo public. `plan.md` does not exist.
- The user commits; do not run `git commit`.

---

## 1. Your role and the mission

You are the lead engineer and design lead on **Groundtruth**, a two-person team's entry to the **Google Cloud AI Builder Cup 2026** (Hack2skill), theme **Sustainability & Social Impact**.

**Groundtruth** helps city engineers in Bengaluru decide which of the city's **369 wards** to cool first, with what intervention, and at what cost. It ranks wards by heat risk from satellite data, answers planning questions in plain language through a team of agents, recommends interventions within a budget, and **verifies every figure against the data before showing it**.

**The one thing judges should remember:**
> "A city engineer could use this tomorrow, every number it shows is verified, and it would work in any city."

**Judging (official weights):**

| Criterion | Weight | What earns it here |
|---|---|---|
| Technical merit & Gen AI | 40% | Multi-agent ADK system on Gemini, live `ST_REGIONSTATS` on Earth Engine data, deterministic verification, a locally fitted cooling-effect model, a measured ablation |
| Problem alignment & impact | 25% | All 369 wards ranked, budget-aware decisions, a named user, one measured impact number |
| Innovation & creativity | 25% | The model never computes numbers; every figure is traced; effects come from local data with uncertainty |
| UX & solution design | 10% | The interface in Section 9 |

**Four differentiators you must protect above all else.** If time runs short, cut other features first.
1. The Verifier, with a visible "N of N figures verified" indicator and clickable sources for every figure.
2. The ablation: Gemini alone vs agents without verification vs full Groundtruth, measured.
3. A budget decision compared with a naive "hottest wards first" allocation.
4. Validation of the ranking against known hot and cool areas.

**Hard competition requirements:** uses Google AI models (Gemini) or an agentic platform; deployed on Google Cloud via **Cloud Run**; working prototype (not a mockup); public GitHub repo; demo video of 3 minutes or less; PDF deck; everything in English.

**Timeline:** today is 23 Sep 2026. Target submission **3 Oct 2026**. Feature freeze **end of 1 Oct**. (The deadline is Oct 4 per the registration email, possibly Oct 18 per the website; plan for Oct 4 unless told otherwise.)

---

## 2. Ground rules (non-negotiable)

1. **Never invent data, results or metrics.** No placeholder numbers presented as real, no mock API responses in the shipped app, no fabricated evaluation scores, quotes or user feedback. If something is not computed yet, the UI says so plainly.
2. **Verify before you use.** Package names, model names, Earth Engine collection IDs, band names, scale factors and API signatures change. Anything marked **(verify)** in this file must be checked against current official documentation before you rely on it. Record what you found in `docs/DECISIONS.md`.
3. **Numbers come from tools, never from the language model.** Gemini plans, routes and writes prose. SQL and Python compute every figure.
4. **Stop and ask** before anything that could cost real money at scale, delete data, change IAM, or make something public.
5. **No secrets in the repo.** Use Application Default Credentials locally and the Cloud Run service account in production. Keep `.env` out of git.
6. **Work in phases** (Section 6). At each exit test, show evidence (query output, test run, screenshot), then commit with a clear message and wait for approval.
7. **Commit early and often** so the history shows the project was built during the hackathon.
8. **Keep notes.** Maintain `docs/DECISIONS.md` (what was chosen and why), `docs/NOTES.md` (running log, problems, fixes) and `docs/RESULTS.md` (only numbers produced by real runs, each with the script and date that produced it).
9. **Critique your own UI.** Use Playwright to take screenshots at 1440 px and 390 px widths after each UI milestone, review them against Section 9, and fix what falls short before reporting.

---

## 3. Environment (already set up and verified)

| Item | Value |
|---|---|
| GCP project | `penumbra-509416` |
| Region for Cloud Run and Vertex AI | `us-central1` (confirm the chosen Gemini model is available there) |
| BigQuery dataset | `penumbra-509416.penumbra` (location **US**) |
| Cloud Storage bucket | `gs://penumbra-509416-penumbra` (location **US**) |
| Service account | `penumbra-app@penumbra-509416.iam.gserviceaccount.com` |
| Its roles | BigQuery Job User, BigQuery Data Editor, Storage Object Admin, Vertex AI User, Earth Engine Resource Viewer, Service Usage Consumer |
| Enabled APIs | BigQuery, Earth Engine, Cloud Storage, Cloud Run, Vertex AI (`aiplatform.googleapis.com`), Artifact Registry, Cloud Build |
| Earth Engine | Project registered |
| Existing Cloud Run service | `penumbra-app` (hello-world from `agents/`) |

**Existing table `penumbra.wards` (369 rows, verified):**
Relevant columns: `id2` (e.g. `ward_369_final.33`, intended unique key; confirm), `ward_id` (ward number), `ward_name`, `ward_name_kn` (Kannada), `Corporation` (Central, East, North, South, West; note the capital C), `corporation_id`, `corporation_kn`, `ac`, `ac_no`, `ac_kn`, `Assembly`, `geometry` (GEOGRAPHY). KML leftovers to ignore: `timestamp`, `begin`, `end`, `icon`, `tessellate`, `drawOrder`, `extrude`, `visibility`, `altitudeMode`, `Name`, `description`, `id`.

**Verified facts about `ST_REGIONSTATS`** (from Google's BigQuery raster documentation):
- Queries must run in `US`, `us-central1`, `us-central2`, `EU` or `europe-west1`. Earth Engine image assets work only with queries in the US region.
- `raster_id` can be an Earth Engine image asset (`'ee://IMAGE_PATH'`, single image only) or a **Cloud Optimized GeoTIFF** in a US or us-central1 bucket (`'gs://bucket/path.tif'`).
- Optional `include` sets pixel weights (0 to 1); optional `options => JSON '{"scale": N}'` resamples.
- Polygons much smaller than a pixel can return null.
- Usage is billed separately; default quota about 350 slot-hours per day.
- Tested already: `ST_REGIONSTATS(geometry, 'ee://USGS/SRTMGL1_003', 'elevation').mean` returns about 886 to 908 m for real wards.

---

## 4. Target repository layout

```
penumbra/
├── CLAUDE.md                 # this file
├── plan.md                   # phase plan
├── README.md                 # filled from real results only
├── Dockerfile                # multi-stage: build frontend, run FastAPI
├── pipeline/                 # data layer (run once, not at request time)
│   ├── 01_prepare_wards.sql
│   ├── 02_export_composites.py
│   ├── 03_zonal_stats.sql
│   ├── 04_population.py
│   ├── 05_infrastructure.sql
│   ├── 06_risk.sql
│   ├── 07_grid_sample.py
│   └── 08_export_geojson.py
├── model/
│   ├── cooling_model.py      # fit, spatial CV, bootstrap effects
│   └── README.md             # method and held-out results
├── server/                   # FastAPI + ADK (Cloud Run service)
│   ├── main.py
│   ├── api/                  # routes
│   ├── agents/               # orchestrator, analyst, planner, verifier
│   ├── tools/                # SQL and Python tools
│   ├── verify/               # deterministic claim checker
│   ├── optimizer/            # budget allocation
│   ├── store.py              # tool_results store
│   └── tests/
├── web/                      # React + TypeScript + Vite
│   ├── src/
│   │   ├── styles/tokens.css
│   │   ├── components/
│   │   ├── pages/
│   │   └── lib/
│   └── public/data/wards.geojson
├── eval/
│   ├── questions.yaml
│   ├── run_eval.py
│   └── results/              # generated only
├── cities/
│   └── bengaluru.yaml        # city pack config
└── docs/
    ├── DECISIONS.md
    ├── NOTES.md
    ├── RESULTS.md
    └── architecture.md
```

Move the current `agents/` hello-world into `server/` when Phase 2 starts, and keep the Cloud Run service name `penumbra-app`.

---

## 5. Stack

| Layer | Choice | Notes |
|---|---|---|
| Agents | Google **Agent Development Kit (ADK)**, Python | (verify) package name and current API. Configure it to use Vertex AI in `penumbra-509416`, `us-central1` |
| Model | Current Gemini model on Vertex AI | (verify) model ID; read it from env var `MODEL_ID`, never hard-code an old name |
| API | FastAPI, Python 3.11+ | Serves `/api/*` and the built frontend |
| Data | BigQuery (`google-cloud-bigquery`), Earth Engine Python API | Read-only at request time |
| Frontend | React + TypeScript + Vite, **MapLibre GL JS**, React Router, TanStack Query | No UI component kit; own components styled from tokens |
| Styling | CSS custom properties + CSS Modules | Tokens in `web/src/styles/tokens.css` |
| Fonts | Google Fonts: **Geologica**, **Hanken Grotesk**, **Noto Sans Kannada** | (verify) availability and that Hanken Grotesk supports tabular figures |
| Tests | pytest (server), Vitest (web), Playwright (screenshots and smoke tests) | |
| Deploy | Single Cloud Run service `penumbra-app`, `us-central1`, runs as `penumbra-app` service account | |

**Map basemap:** render ward polygons on the app background with no third-party tiles by default. This keeps the map fast, license-free and visually ours. If you add a basemap later, check its terms first and keep it very muted.

---

## 6. Build phases

Each phase ends with an exit test. Show the evidence, commit, and wait for approval.

### Phase 1: Data layer (23 to 25 Sep)

1. **`01_prepare_wards.sql`**
   - Confirm `COUNT(DISTINCT id2) = 369` and 5 corporations. If `id2` is not unique, stop and report.
   - Create a clean `wards_clean` table: `city_id = 'bengaluru'`, `ward_key` (= `id2`), `ward_no`, `ward_name`, `ward_name_kn`, `corporation`, `corporation_kn`, `ac`, `ac_no`, `geometry`, `area_km2` (`ST_AREA/1e6`), `centroid`.
   - Check `ST_ISVALID(geometry)` for all rows; repair or report invalid ones.

2. **`02_export_composites.py`** (Earth Engine Python API)
   - Region: bounding box of all wards plus a 1 km buffer.
   - Years: a baseline year and 2025. Prefer 2016 as baseline if the chosen land-cover source starts mid-2015; otherwise 2015. Document the choice.
   - Season: pre-monsoon, March to May. Inspect cloud cover first; widen to January to May only if needed, and record it.
   - Source: Landsat 8 and 9 Collection 2 Level 2 (verify IDs, e.g. `LANDSAT/LC08/C02/T1_L2`, `LANDSAT/LC09/C02/T1_L2`).
   - Cloud and shadow mask from `QA_PIXEL` (verify bit positions).
   - Land surface temperature: surface temperature band to °C (verify band name, scale factor and offset; typically `ST_B10 × 0.00341802 + 149.0 − 273.15`).
   - NDVI from surface reflectance NIR and red bands (verify band names, scale and offset).
   - Built-up fraction: from a land-cover product available for both years (e.g. Dynamic World built probability, or GHSL built surface; verify coverage and license).
   - Valid-pixel count per composite.
   - Median composites. **Export one single-band Cloud Optimized GeoTIFF per layer per year** to `gs://penumbra-509416-penumbra/rasters/{layer}_{year}.tif` at 30 m. Single-band files avoid ambiguity about band names in `ST_REGIONSTATS`.
   - Start all exports first, then do other work while they run. Log task IDs.

3. **`03_zonal_stats.sql`**
   - For each ward, layer and year, call `ST_REGIONSTATS(geometry, 'gs://.../{layer}_{year}.tif')` and keep `mean`, plus `min`, `max`, `count` where useful. Also compute the 90th percentile of LST if the function supports it (verify); otherwise skip it.
   - Write `ward_metrics`: `city_id, ward_key, year, lst_mean_c, lst_max_c, ndvi_mean, built_frac, valid_pixel_count, valid_pixel_frac`.
   - Sanity check: all 369 wards present per year; LST values plausible for Bengaluru in pre-monsoon; report any nulls.
   - If exports fail, fall back to computing zonal statistics in Earth Engine and exporting the table to BigQuery; record the change.

4. **`04_population.py`**: load OpenCity's ward population data for the 2025 delimitation (verify the resource and its columns). Join to `wards_clean` by ward number and corporation; report unmatched wards rather than guessing.

5. **`05_infrastructure.sql`**: hospitals and schools from Overture Maps places in BigQuery public data (verify table and category names and license). Assign each to a ward with `ST_WITHIN`. Table `infra_points`.

6. **`06_risk.sql`**: table `ward_risk` per ward and year:
   - `heat_score` = percentile rank of `lst_mean_c`
   - `green_deficit` = 1 − percentile rank of `ndvi_mean`
   - `built_pressure` = percentile rank of `built_frac`
   - `exposure_score` = percentile rank of population density
   - `composite_risk` = weighted sum; default weights 0.4 / 0.2 / 0.15 / 0.25 (heat, green, built, exposure); store weights used
   - `rank` within city, and `delta_lst_c` between baseline and 2025
   - Also a view that recomputes the composite for arbitrary weights (for the UI sliders)

7. **Validation note** in `docs/RESULTS.md`: list the 10 coolest and 10 hottest wards and check them against known large lakes, parks and dense commercial or industrial areas. Record honestly where the ranking agrees and where it does not. Run a weight-sensitivity check (Spearman correlation of ranks under ±0.1 weight changes).

8. **`08_export_geojson.py`**: export simplified ward polygons (`ST_SIMPLIFY`, about 10 to 20 m) with `ward_key`, names and corporation to `web/public/data/wards.geojson`. Keep it under 1.5 MB.

**Exit test:** one query returns 369 wards with 2025 LST, NDVI, built-up, population, composite risk, rank and change since baseline; the validation note exists; the GeoJSON renders in a quick MapLibre test page.

### Phase 2: Agent core with verification (25 to 27 Sep)

1. **Tool result store** (`server/store.py`): every tool call gets a `tool_result_id` (UUID), its tool name, parameters, result JSON and timestamp. Keep an in-memory map for the request and write asynchronously to BigQuery table `tool_results` for audit and the source drawer.

2. **Tools** (`server/tools/`), parameterized SQL only, read-only, `maximum_bytes_billed` set on every job:
   - `get_ward_metrics(city_id, ward_key, year)`
   - `find_ward(city_id, name_query)` (fuzzy match on English and Kannada names; returns candidates, never guesses silently)
   - `rank_wards(city_id, metric, n, year, corporation=None, order='desc')` where metric is from an allow-list
   - `compare_years(city_id, ward_keys, metric, year_a, year_b)`
   - `corporation_summary(city_id, corporation, year)`
   - `nearby_facilities(city_id, ward_key, type)`
   - `live_regionstats(ward_key, layer, year)` (the one live Earth Engine call, for the demo)
   Every tool returns `{tool_result_id, data}`.

3. **Agents** (ADK):
   - **Orchestrator**: understands the question, plans steps, delegates, and produces the final answer in the claim format below. It must not state any number that is not from a tool result.
   - **Geospatial Analyst**: calls data tools.
   - **Intervention Planner**: added in Phase 3.
   - **Verifier**: runs the deterministic checker (below). It may additionally use Gemini to flag wording that contradicts a figure (for example "cooled" when `delta_lst_c` is positive), but the numeric check is always code.

4. **Answer format** returned by the Orchestrator:

```json
{
  "narrative": "Ward {c1} warmed the most since 2016, by {c2}.",
  "claims": [
    {"id": "c1", "text": "Bellandur", "kind": "entity", "tool_result_id": "…", "path": "data[0].ward_name"},
    {"id": "c2", "text": "3.1 °C", "kind": "number", "value": 3.1, "unit": "°C", "tool_result_id": "…", "path": "data[0].delta_lst_c"}
  ],
  "highlight_ward_keys": ["ward_369_final.12"]
}
```
   (Example values are illustrative formatting only, not data.)

5. **Deterministic verifier** (`server/verify/`):
   - For each claim: look up the tool result, resolve `path`, compare value within tolerance (absolute 0.05 for °C, relative 0.5% otherwise, after rounding to displayed precision), check unit.
   - Every `{cN}` placeholder in the narrative must map to a claim; every number-looking token in the narrative outside placeholders fails verification.
   - Unverifiable claims are removed and the sentence is rewritten or dropped; return `verification: {verified, total, removed: [...]}`.
   - Unit tests for pass, fail, missing path, unit mismatch and stray numbers.

6. **API**
   - `GET /api/health`
   - `GET /api/wards?year=2025` → list for the map and ranking
   - `GET /api/wards/{ward_key}` → detail
   - `GET /api/risk?weights=...&year=...` → reweighted ranking
   - `POST /api/ask` `{question, city_id, session_id}` → `{narrative, claims, verification, trace, highlight_ward_keys}`; stream trace events with Server-Sent Events if practical, otherwise return them at the end
   - `GET /api/sources/{tool_result_id}` → tool, parameters, result, timestamp
   - Guardrails: at most 8 tool calls per question, 45-second timeout, simple per-IP rate limit, refuse street- or property-level claims with an explanation.

7. Deploy to Cloud Run with `--service-account penumbra-app@penumbra-509416.iam.gserviceaccount.com`.

**Exit test:** on the deployed URL, `POST /api/ask` with "Which five wards in the East corporation warmed most since the baseline year?" returns five real wards with all figures verified; unit tests pass.

### Phase 3: Decision layer (27 to 29 Sep)

1. **Cooling-effect model** (`pipeline/07_grid_sample.py`, `model/cooling_model.py`):
   - Sample a 150 m grid across the city from the 2025 composites: LST, NDVI, built fraction, elevation, distance to nearest water body (from a water mask; verify source).
   - Fit an interpretable model (regularized linear or a GAM with few splines).
   - **Spatial block cross-validation** (about 1 km blocks, grouped folds). Report held-out R² and error in `model/README.md` and `docs/RESULTS.md`.
   - Bootstrap effect ranges (low, mid, high) for a change in NDVI and in built fraction.
   - Store in BigQuery `effect_model`. Label everything as **associations with surface temperature**, not guaranteed outcomes. If held-out skill is weak, say so in the UI and widen ranges; never hide it.

2. **Intervention catalog** (`intervention_catalog` table and `cities/bengaluru.yaml`): tree canopy, lake and wetland buffer restoration, cool roofs, permeable paving, pocket parks. For each: unit, how it changes model inputs (stated assumption), applicability rule (e.g. cool roofs only where built fraction is high), default unit cost in INR with `cost_source` or `assumption: true`, and guidance citations.

3. **Guidance retrieval**: index a small set of public documents (Bengaluru climate action and resilience plans, published urban-heat studies; confirm each is public and cite page numbers). Keep retrieval simple and inspectable; every recommendation cites at least one passage.

4. **Intervention Planner agent**: for a ward, choose applicable interventions, attach effect ranges (from `effect_model`, via a tool) and citations.

5. **Budget optimizer** (`server/optimizer/`, plain Python, no model): maximize population-weighted modeled cooling (person-°C) per rupee under the budget and per-ward caps; greedy with marginal benefit is fine. Also compute the **naive allocation** (fund the hottest wards first with the same interventions). Return both with the assumptions used, as a tool result.

6. **Ward brief**: `GET /api/brief/{ward_key}?lang=en|kn` returns structured content; the web app renders a print-ready page (A4 print stylesheet) that the browser saves as PDF. Kannada uses the existing `ward_name_kn` and translated section labels; mark machine-translated prose as such.

7. `POST /api/plan` `{budget_inr, scope: {city|corporation}, cost_overrides}` → `{allocation, naive, comparison, assumptions, tool_result_id}`.

**Exit test:** on the deployed service, a plan for one corporation and a budget returns an allocation, the naive comparison and a brief, with all figures verified and assumptions listed.

### Phase 4: Frontend (28 Sep to 1 Oct)

Build to the design system in Section 9. Pages and behavior in Section 10.

**Exit test:** Playwright screenshots at 1440 px and 390 px for every page look deliberate and match Section 9; a first-time user can find the riskiest ward in their corporation, ask a question, open a figure's source and export a brief without help. **Feature freeze at the end of 1 Oct.**

### Phase 5: Proof (30 Sep to 2 Oct)

1. `eval/questions.yaml`: at least 15 questions across lookup, ranking, change over time, corporation filter and budget. Each has `expected_sql` run directly against BigQuery by `run_eval.py`. Never write expected answers by hand.
2. Run three configurations: **Gemini alone (no tools)**, **agents without verification**, **full Groundtruth**. Record numeric accuracy, answers containing unsupported figures, latency and cost per question. Save raw outputs in `eval/results/` and a summary in `docs/RESULTS.md`.
3. Time three planning questions answered manually with standard tools (or state an explicit assumption) versus Groundtruth.
4. Record the optimizer versus naive comparison for one realistic budget, with assumptions.
5. Surface these results on the Method page directly from the results files.

**Exit test:** every number planned for the video and deck exists in `docs/RESULTS.md` with the script and date that produced it.

### Phase 6: Ship (2 to 3 Oct)

1. README filled from real results; architecture diagram; setup steps; data sources and licenses (OpenCity ward data is listed as ODbL-1.0 on bharatlas; confirm); limitations.
2. Cloud Run: `--min-instances=1` during judging; test on a fresh browser profile and a phone; a cached-answer fallback for the demo questions is allowed only if it shows a visible "saved answer from [timestamp]" label.
3. Help me with the video script and deck outline (plan.md Section 5, Phase 6).

---

## 7. Data honesty rules for the product

- Show units everywhere. Show data year and season next to every map.
- Show `valid_pixel_frac` in ward detail; if it is below 0.5, show a coverage warning.
- Land surface temperature is not air temperature. Say "surface temperature" in the UI, never "temperature" alone.
- Effects are "modeled association" with a range, never a promise.
- Costs flagged as assumptions display as "assumed cost" until sourced.
- No claims below ward level.

---

## 8. What not to do

- No generic chatbot page with a blank input and nothing else.
- No fake loading spinners that hide nothing; progress states must reflect real steps.
- No dashboards of charts nobody asked for. Every chart must answer a planner's question.
- No hard-coded numbers in the UI copy.
- No UI component kit defaults, no stock illustrations, no emoji in the interface.
- No free-form SQL generated by the model at request time.
- Do not rename the Cloud Run service or change IAM without asking.

---

## 9. Design system: "Shade"

### Concept
Groundtruth means the partial shadow between full light and full shade. The interface is built on that idea: **the city's heat is warm and bright; the interface is cool and shaded; the product's job is to move wards from light into shade.** Heat colors appear only where they encode data. Everything else lives in cool, quiet greens and slate blues taken from Bengaluru's rain trees and monsoon sky.

The subject is civic and serious. The audience is ward engineers and planners who need to trust what they see. The primary job of every screen is to help someone make and defend a decision.

**Spend boldness in one place: the map.** It is large, uncluttered and beautifully colored. Everything around it is calm and disciplined.

### Color tokens

Base palette (light theme, default):

| Token | Hex | Use |
|---|---|---|
| `--mist` | `#E9EEEA` | App background, the "shade" the map sits on |
| `--leaf-paper` | `#F7F9F6` | Panels, sheets, inputs |
| `--rain-tree` | `#17302C` | Primary text, ward outlines at high zoom |
| `--lichen` | `#5C6F69` | Secondary text, axes, hints (check it passes 4.5:1 on both backgrounds) |
| `--canopy` | `#2E6A4E` | Cooling, interventions, verified figures, primary buttons |
| `--monsoon` | `#2F5F84` | Links, focus rings, selection, interactive map outline |
| `--hairline` | `#CAD3CE` | Dividers and borders (use sparingly) |

Heat ramp for surface-temperature risk (sequential, 7 bins, light to dark so it also reads in grayscale). Base it on ColorBrewer YlOrRd, which is designed for sequential data and remains distinguishable for common color-vision deficiencies:

| Bin | Hex |
|---|---|
| 1 (coolest) | `#FFFFB2` |
| 2 | `#FED976` |
| 3 | `#FEB24C` |
| 4 | `#FD8D3C` |
| 5 | `#FC4E2A` |
| 6 | `#E31A1C` |
| 7 (hottest) | `#B10026` |

Change-over-time ramp (diverging, for "change since baseline"): cooling side in monsoon blues, warming side in heat tones, neutral at zero: `#2F5F84`, `#8FB3CC`, `#E4EAE6`, `#FDB27A`, `#D7301F`. Always show the zero point and numeric labels.

Dark theme (for evening demos and user preference): background `#12211E`, panels `#1A2E2A`, text `#E6EEEA`, secondary `#9DB2AA`, canopy `#5FB38A`, monsoon `#7FB1D8`, hairline `#2C433E`. Keep the heat ramp unchanged; give ward outlines a thin `#12211E` stroke so bins stay separable.

Implement as CSS custom properties on `:root`, with a `[data-theme="dark"]` override and a `prefers-color-scheme` default. Verify all text contrast meets WCAG AA.

### Typography

| Role | Face | Setting |
|---|---|---|
| Headings, ward names, the big figure in ward detail | **Geologica**, weight 600, slight negative tracking at large sizes | Its geometric, map-like shapes suit a geographic tool |
| Interface and body | **Hanken Grotesk**, 400 and 500 | Tabular figures (`font-variant-numeric: tabular-nums`) for every number |
| Kannada text | **Noto Sans Kannada** | Same sizes; line-height about 1.6 |

Type scale (rem, base 16 px): 0.8125, 0.875, 1, 1.125, 1.375, 1.75, 2.25, 3. Body line-height 1.5, headings 1.15. Body line length under 72 characters. Sentence case everywhere. Do not use all-caps labels, tracked-out eyebrow text above headings, italicized single words in headlines, monospace for data labels, or arrows appended to button text.

### Shape, space and depth

- Spacing scale: 4, 8, 12, 16, 24, 32, 48, 64 px.
- Radius follows hierarchy: 4 px for inputs and chips, 10 px for panels and sheets, full round only for toggles. Not one radius everywhere.
- Depth comes from **shade, not shadow boxes**: panels sit on the mist background with a very soft, large, tinted shadow (`0 12px 32px rgba(23, 48, 44, 0.10)`) only when they float over the map (sheets, popovers). Static panels have no shadow.
- Avoid rows of identical cards. Use lists, tables and the map as the main structures.

### The signature moment (the one orchestrated animation)

When a plan is applied in the Budget planner, a **shade sweep** passes across the map once: a soft diagonal band, dark at its core and fading at the edges like a penumbra, travels across the city over about 900 ms. As it passes each ward in the plan, that ward's fill transitions from its current heat bin toward its modeled bin, and its outline turns canopy green. Wards not in the plan stay as they are. This is the only non-trivial animation in the product.
- Everything else uses short, functional transitions (150 to 200 ms) that answer a user action: sheets opening, a figure's source drawer expanding, a ranking reordering.
- With `prefers-reduced-motion: reduce`, skip the sweep and switch fills directly.
- No page-load sequences, no fade-and-slide on every section, no hover effects on every item.

### Figures as receipts

Every verified figure in an answer, a ward brief or a plan appears as an inline **figure chip**: the value in tabular figures with a thin canopy underline. Clicking or pressing Enter opens a **source drawer** showing, in plain language, where it came from ("Ranked wards by change in surface temperature, East corporation, 2016 to 2025"), the tool name, parameters, the raw value, and the time it was computed. The answer footer reads, for example, "12 of 12 figures verified" with a canopy check. If any were removed, the footer says how many and why.

### Map styling

- Ward fills from the heat ramp with 0.9 opacity; ward borders `--leaf-paper` at 0.75 px; corporation borders `--rain-tree` at 1.5 px.
- Hover: outline in `--monsoon`, 2 px; no fill change. Selected: 2.5 px `--rain-tree` outline and a subtle inner glow.
- Legend in the lower left: seven bins with real °C boundaries from the data (quantile bins by default; state the method), data year and season, and "Surface temperature, not air temperature".
- Ward labels appear only at zoom levels where they fit, in Hanken Grotesk 500 with a mist halo.
- Keyboard alternative: the ranked list is fully keyboard navigable and selecting a row selects the ward on the map.

### Copy voice

Plain, specific, active. Buttons say exactly what happens: "Ask Groundtruth", "Run plan", "Export ward brief", "Show source". The same action keeps the same name throughout ("Run plan" → toast "Plan ready"). Errors say what happened and what to do, without apologizing. Empty states invite action.

Examples:
- Empty Ask panel: "Ask about any ward, corporation or change since 2016. Try one of these." followed by three real suggested questions.
- Timeout: "Groundtruth took longer than 45 seconds. Try a narrower question, such as one corporation."
- No coverage: "Clouds hid most of this ward in the 2016 images, so its baseline value is uncertain."

---

## 10. Pages and components

Navigation (top bar, left aligned): **Groundtruth** wordmark in Geologica, then "Map", "Ask", "Plan", "Method". Right side: city ("Bengaluru"), year, theme toggle, English/ಕನ್ನಡ toggle for ward names.

### Map (home)

```
+-----------------------------------------------------------------------------+
| Groundtruth   Map  Ask  Plan  Method                 Bengaluru  2025  ◐  EN/ಕ |
+--------------------------------------------------+--------------------------+
|                                                  | Wards by heat risk       |
|                                                  | Corporation: All ▾       |
|              369-ward heat map                   | 1  Ward name     score   |
|        (left-aligned, full height)               | 2  Ward name     score   |
|                                                  | ...                      |
|                                                  | Adjust weights ▸         |
| Legend: 7 bins, °C, year, season                 |                          |
+--------------------------------------------------+--------------------------+
```
- View switch above the map: "Heat risk", "Surface temperature", "Change since 2016", "Green cover".
- Ranked list is a true ranking (numbers are meaningful). Each row: rank, ward name (EN or KN), corporation, the chosen metric with unit, and a tiny inline bar.
- "Adjust weights" expands four sliders with live re-ranking via `/api/risk`; "Reset to default weights".
- Selecting a ward opens the **ward sheet** over the map (right side on desktop, bottom sheet on mobile).

### Ward sheet (detail)

- Header: ward name in Geologica (English with Kannada beneath), corporation, assembly constituency.
- One large figure: 2025 surface temperature with its difference from the city median, as a figure chip.
- Small multiples: LST, green cover, built-up, each with 2016 and 2025 and the change.
- Nearby facilities: count of hospitals and schools.
- Recommended actions (from Phase 3), each with effect range, assumed cost and citation.
- Coverage note if needed.
- Buttons: "Export ward brief", "Ask about this ward" (prefills Ask).

### Ask

```
+--------------------------------+--------------------------------------------+
| Conversation                   | Map highlighting wards in the answer       |
|                                |                                            |
|  Question                      |                                            |
|  Answer with figure chips      +--------------------------------------------+
|  12 of 12 figures verified     | How this answer was made                   |
|                                | 1 Planned the steps                        |
|                                | 2 Ranked East wards by change      0.8 s   |
| [ Ask about any ward… ]  Ask   | 3 Checked 12 figures               0.2 s   |
+--------------------------------+--------------------------------------------+
```
- The trace is a real sequence (numbering is appropriate here), streamed as steps complete, with durations.
- Suggested questions are real questions the system answers well (taken from the eval set).
- Figure chips open the source drawer.

### Plan

- Left: map. Right: controls: scope (city or corporation), budget in INR, intervention list with editable assumed costs, "Run plan".
- Result: the shade sweep on the map, then an allocation table (ward, intervention, amount, modeled cooling range, people covered) and a comparison block: "This plan vs funding the hottest wards first", with person-°C and people covered for both, as figure chips.
- Assumptions listed plainly under the result.

### Method

- Readable long-form page, max 70 characters per line, Hanken Grotesk body with Geologica headings.
- Sections: what Groundtruth measures; data sources with dates and licenses; how the risk score works; the cooling model and its held-out performance; the evaluation and ablation results (rendered from `docs/RESULTS.md` data, not typed by hand); limitations.

### Ward brief (print)

- A4 print stylesheet, one or two pages: ward name (EN and KN), corporation, data year, key figures with sources as footnotes, recommended actions with ranges and costs, assumptions, limitations, generated date.

### Components to build

`TopBar`, `CityYearSwitch`, `ThemeToggle`, `LangToggle`, `WardMap`, `MapLegend`, `ViewSwitch`, `RankedList`, `WeightSliders`, `WardSheet`, `FigureChip`, `SourceDrawer`, `VerificationFooter`, `AgentTrace`, `AskComposer`, `SuggestedQuestions`, `PlanControls`, `AllocationTable`, `ComparisonBlock`, `CoverageNote`, `EmptyState`, `ErrorState`, `PrintBrief`.

### Quality floor

- Responsive down to 360 px; on mobile the map is full width and panels become bottom sheets.
- Visible focus (2 px `--monsoon` ring with offset) on every interactive element.
- Color is never the only signal: legends have numbers; verified status has a check and text.
- Loading states name the real step; skeletons only where the layout is known.
- Lighthouse accessibility score 95 or above; check contrast of every token pair used for text.

---

## 11. Deployment

- Multi-stage `Dockerfile`: build `web/` with Node, copy the `dist/` into the Python image, FastAPI serves it at `/` and the API at `/api`.
- Deploy:

```bash
gcloud run deploy penumbra-app \
  --source . \
  --region us-central1 \
  --project penumbra-509416 \
  --service-account penumbra-app@penumbra-509416.iam.gserviceaccount.com \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT=penumbra-509416,GOOGLE_CLOUD_LOCATION=us-central1,BQ_DATASET=penumbra,MODEL_ID=<verified model id>
```
  (verify the environment variables ADK expects for Vertex AI.)
- Health check on `/api/health`. Structured logs with request IDs. Set a billing budget alert (ask me first).

---

## 12. Definition of done

- [ ] Deployed Cloud Run URL works on a fresh browser and a phone
- [ ] Map, Ask, Plan, Method and ward brief all work on real data
- [ ] Every figure in every answer is verified or removed, and sources open
- [ ] Ablation, validation, cooling-model held-out results and impact numbers exist in `docs/RESULTS.md` from real runs
- [ ] Limitations visible in the product and README
- [ ] Unit tests pass; Playwright smoke test passes against the deployed URL
- [ ] README complete, public repo clean, no secrets
- [ ] Screenshots at 1440 px and 390 px reviewed against Section 9

---

## 13. How to report to me

At the end of each phase, send:
1. What was built (short list).
2. Exit-test evidence (query output, test results, screenshots).
3. Anything you verified or changed from this brief, and why (also in `docs/DECISIONS.md`).
4. Risks for the next phase and what you would cut if we fall behind.

If you are ever unsure whether something is real data or an assumption, treat it as an assumption and label it.
