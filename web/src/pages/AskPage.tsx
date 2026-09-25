import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AgentTrace } from "../components/AgentTrace";
import { FigureChip } from "../components/FigureChip";
import { MapLegend } from "../components/MapLegend";
import { EmptyState, ErrorState } from "../components/States";
import { VerificationFooter } from "../components/VerificationFooter";
import { WardMap } from "../components/WardMap";
import { api, type AskResponse } from "../lib/api";
import { classify } from "../lib/bins";
import { useCorporationShapes, useWardShapes, useWards } from "../lib/data";
import { splitTemplate } from "../lib/narrative";
import { BASELINE_YEAR, CURRENT_YEAR, usePrefs } from "../lib/prefs";
import { type Results, useResults } from "../lib/results";
import { mapViews } from "../lib/views";
import styles from "./AskPage.module.css";

// Suggestions come from the evaluation set (eval/questions.yaml): these
// three, shown only if full Penumbra answered each correctly in the latest
// run (results.json). Otherwise fall back to questions verified in live
// tests (docs/NOTES.md).
const FALLBACK_SUGGESTED = [
  "Which five wards in the East corporation warmed most since the baseline year?",
  `What is the surface temperature and green cover of Padarayanapura in ${CURRENT_YEAR}?`,
  `How many people live in the West corporation and what is its average surface temperature in ${CURRENT_YEAR}?`,
];
const SUGGESTED_IDS = ["change_east_warmed_five", "corp_west_summary", "budget_east_50cr"];

function suggestedFrom(r: Results | undefined): string[] {
  const qs = r?.evaluation?.questions ?? [];
  const picked = SUGGESTED_IDS.map((id) => qs.find((q) => q.id === id && q.penumbra.correct)?.question).filter((q): q is string => !!q);
  return picked.length === SUGGESTED_IDS.length ? picked : FALLBACK_SUGGESTED;
}

interface Turn {
  id: number;
  question: string;
  startedAt: number;
  response?: AskResponse;
  error?: string;
}

function Elapsed({ since }: { since: number }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(t);
  }, []);
  return <span className="num">{((now - since) / 1000).toFixed(0)} s</span>;
}

function Answer({ response }: { response: AskResponse }) {
  const claims = useMemo(() => new Map(response.claims.map((c) => [c.id, c])), [response.claims]);
  const segments = splitTemplate(response.narrative_template ?? response.narrative);
  return (
    <div className={styles.answer}>
      <p className={styles.narrative}>
        {segments.map((s, i) => {
          if (s.kind === "text") return <span key={i}>{s.text}</span>;
          const c = claims.get(s.id);
          if (!c) return null;
          return (
            <FigureChip key={i} toolResultId={c.tool_result_id} path={c.path} label={c.kind === "entity" ? "Ward or place named in the answer" : undefined}>
              {c.text}
            </FigureChip>
          );
        })}
      </p>
      <VerificationFooter verification={response.verification} />
    </div>
  );
}

export function AskPage() {
  const { theme, lang } = usePrefs();
  const [params, setParams] = useSearchParams();
  const [input, setInput] = useState(() => params.get("q") ?? "");
  const [turns, setTurns] = useState<Turn[]>([]);
  const nextId = useRef(1);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const sessionId = useRef<string | undefined>(undefined);

  const shapes = useWardShapes();
  const corps = useCorporationShapes();
  const wards = useWards(CURRENT_YEAR);
  const suggested = suggestedFrom(useResults().data);
  const view = useMemo(() => mapViews(BASELINE_YEAR).risk, []);
  const values = useMemo(() => (wards.data ?? []).map(view.value), [wards.data, view]);
  const classification = useMemo(() => view.classify(values), [view, values]);
  const bins = useMemo(() => new Map((wards.data ?? []).map((r, i) => [r.ward_key, classify(values[i], classification)])), [wards.data, values, classification]);

  useEffect(() => {
    if (params.get("q")) {
      inputRef.current?.focus();
      const next = new URLSearchParams(params);
      next.delete("q");
      setParams(next, { replace: true });
    }
    // Only on first load: move a prefilled question from the URL into the box.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [turns]);

  const pending = turns.some((t) => !t.response && !t.error);
  const latest = [...turns].reverse().find((t) => t.response);

  const ask = async (question: string) => {
    const q = question.trim();
    if (!q || pending) return;
    const id = nextId.current++;
    setTurns((t) => [...t, { id, question: q, startedAt: Date.now() }]);
    setInput("");
    try {
      const response = await api.ask(q, sessionId.current);
      sessionId.current = response.session_id;
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, response } : x)));
    } catch (e) {
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, error: (e as Error).message } : x)));
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void ask(input);
  };

  return (
    <div className={styles.page}>
      <section className={styles.conversation} aria-labelledby="ask-title">
        <h1 id="ask-title" className="visually-hidden">
          Ask Penumbra
        </h1>
        <div className={styles.thread} aria-live="polite">
          {turns.length === 0 && (
            <EmptyState title={`Ask about any ward, corporation or change since ${BASELINE_YEAR}. Try one of these.`}>
              <ul className={styles.suggestions}>
                {suggested.map((q) => (
                  <li key={q}>
                    <button type="button" className={styles.suggestion} onClick={() => void ask(q)}>
                      {q}
                    </button>
                  </li>
                ))}
              </ul>
              <p className={styles.fine}>
                Every figure in an answer is checked against the data before you see it. Select a figure to see where it came from. Penumbra answers at ward level
                and above.
              </p>
            </EmptyState>
          )}
          {turns.map((t) => (
            <article key={t.id} className={styles.turn}>
              <p className={styles.question}>{t.question}</p>
              {t.response && <Answer response={t.response} />}
              {t.error && <ErrorState message={t.error} onRetry={() => void ask(t.question)} />}
              {!t.response && !t.error && (
                <p className={styles.pending} role="status">
                  <span className={styles.pulse} aria-hidden="true" />
                  <span>
                    Planning the steps and querying the ward data, <Elapsed since={t.startedAt} />. The steps are listed when the answer is ready.
                  </span>
                </p>
              )}
            </article>
          ))}
          <div ref={endRef} />
        </div>
        <form className={styles.composer} onSubmit={onSubmit}>
          <label htmlFor="ask-input" className="visually-hidden">
            Your question
          </label>
          <textarea
            id="ask-input"
            ref={inputRef}
            className={styles.input}
            rows={2}
            value={input}
            placeholder={`Ask about any ward, corporation or change since ${BASELINE_YEAR}`}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void ask(input);
              }
            }}
          />
          <button type="submit" className="btn btn-primary" disabled={pending || !input.trim()}>
            Ask Penumbra
          </button>
        </form>
      </section>

      <section className={styles.side} aria-label="Wards in the answer and how it was made">
        <div className={styles.map}>
          {shapes.data && wards.data && (
            <WardMap
              shapes={shapes.data}
              corporations={corps.data}
              bins={bins}
              ramp={view.ramp}
              theme={theme}
              lang={lang}
              highlightKeys={latest?.response?.highlight_ward_keys}
              ariaLabel="Map of wards coloured by heat risk. Wards named in the latest answer are outlined in blue."
            />
          )}
          {wards.data && (
            <MapLegend
              view={view}
              classification={classification}
              year={CURRENT_YEAR}
              season="Pre-monsoon (March to May)"
              wardCount={wards.data.length}
              modeledNote={latest?.response?.highlight_ward_keys.length ? "Blue outlines mark the wards in the latest answer." : view.note}
            />
          )}
        </div>
        <div className={styles.trace}>
          <h2 className={styles.h2}>How this answer was made</h2>
          {latest?.response ? (
            <AgentTrace steps={latest.response.trace} />
          ) : (
            <p className={styles.fine}>The agents' steps, with how long each took, appear here after an answer.</p>
          )}
        </div>
      </section>
    </div>
  );
}
