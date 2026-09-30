"use client";

import { AnimatePresence, motion, useInView, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import {
  FINISH_HOLD_MS, PASS_STAGE_MS, PROVENANCE_TAG, STAGES, VERB_MS,
  liveRun, nextStage, stageAnnouncement, verbAt, type PipelineStage,
} from "@/lib/pipeline";
import type { Candidate } from "@/lib/types";

const GLYPHS: Record<PipelineStage["id"], ReactNode> = {
  pdf: <path d="M14 11h11l5 5v17H14zM25 11v5h5M18 24h8M18 28h8" />,
  text: <path d="M13 15h18M22 15v16M18 31h8" />,
  skills: <path d="M13 15h18M13 22h12M13 29h15" />,
  gaps: <path d="M12 31h7v-7h7v-7h6" />,
  courses: <path d="m13 16 2 2 4-4M23 16h9M13 27l2 2 4-4M23 27h9" />,
};

const TRAVEL_S = 0.8;

/** Orientation follows the CSS container query: read it back from the computed flex direction. */
function useVertical(ref: React.RefObject<HTMLElement | null>): boolean {
  const [vertical, setVertical] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const read = () => setVertical(getComputedStyle(el).flexDirection === "column");
    read();
    const observer = new ResizeObserver(read);
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);
  return vertical;
}

type NodeState = "rest" | "done" | "active";

function Node({ step, state, arrive, pulse }: { step: PipelineStage; state: NodeState; arrive: boolean; pulse: boolean }) {
  const dash = step.provenance === "modelo" ? "4 3" : undefined;
  return (
    <svg
      className={`pipe-node ${state === "active" ? "pipe-node--active" : ""}`}
      style={{ "--arrive": arrive ? `${TRAVEL_S * 0.85}s` : "0s" } as CSSProperties}
      width="44" height="44" viewBox="0 0 44 44" aria-hidden="true" focusable="false"
    >
      {pulse && (
        <motion.rect
          className="pipe-ring" x="1" y="1" width="42" height="42" strokeDasharray={dash}
          style={{ transformBox: "fill-box", transformOrigin: "center" }}
          initial={{ scale: 1, opacity: 0.45 }}
          animate={{ scale: 1.32, opacity: 0 }}
          transition={{ duration: 1.5, ease: "easeOut", repeat: Infinity }}
        />
      )}
      <rect x="1" y="1" width="42" height="42" strokeDasharray={dash} />
      <g className="pipe-glyph">{GLYPHS[step.id]}</g>
      {state === "done" && (
        <motion.g className="pipe-check" transform="translate(40 4)"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2, ease: "easeOut" }}>
          <circle r="7" />
          <motion.path d="M-3.5 0.3 -1 2.8 3.5 -2.6"
            initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.25, ease: "easeOut", delay: 0.05 }} />
        </motion.g>
      )}
    </svg>
  );
}

type ConnState = "rest" | "done" | "travelling" | "upcoming";

function Connector({ state, vertical, reduce }: { state: ConnState; vertical: boolean; reduce: boolean }) {
  const d = vertical ? "M22 0V100" : "M0 22H100";
  const drawn = state === "rest" || state === "done";
  const dur = reduce ? 0 : TRAVEL_S;
  return (
    <div className="pipe-conn" aria-hidden="true">
      <svg viewBox={vertical ? "0 0 44 100" : "0 0 100 44"} preserveAspectRatio="none" focusable="false">
        {(state === "upcoming" || state === "travelling") && <path className="pipe-conn-base" d={d} />}
        <motion.path
          d={d}
          initial={false}
          animate={{ pathLength: drawn || state === "travelling" ? 1 : 0 }}
          transition={{ duration: state === "travelling" ? dur : 0, ease: "easeOut" }}
        />
      </svg>
      {state === "travelling" && !reduce && (
        <motion.svg
          key={vertical ? "v" : "h"}
          className={`pipe-packet ${vertical ? "pipe-packet--v" : ""}`}
          width="9" height="9" viewBox="0 0 9 9" focusable="false"
          initial={vertical ? { top: "0%", opacity: 1 } : { left: "0%", opacity: 1 }}
          animate={vertical ? { top: "100%", opacity: [1, 1, 0] } : { left: "100%", opacity: [1, 1, 0] }}
          transition={{ duration: TRAVEL_S, ease: "easeOut", opacity: { duration: TRAVEL_S, times: [0, 0.85, 1] } }}
        >
          <circle cx="4.5" cy="4.5" r="4.5" />
        </motion.svg>
      )}
    </div>
  );
}

function ProvenanceMarker({ modelo }: { modelo: boolean }) {
  return (
    <svg width="18" height="10" viewBox="0 0 18 10" aria-hidden="true" focusable="false">
      <path d="M0 5h18" strokeDasharray={modelo ? "4 3" : undefined} />
    </svg>
  );
}

interface Props {
  candidates: Candidate[];
}

export default function PipelineDiagram({ candidates }: Props) {
  const reduce = useReducedMotion() ?? false;
  const root = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const vertical = useVertical(list);
  const inView = useInView(root, { once: true, amount: 0.4 });

  const run = liveRun(candidates);
  const runId = run?.id ?? null;
  const [pass, setPass] = useState<number | null>(null);
  const [finishing, setFinishing] = useState(false);
  const [tick, setTick] = useState(0);
  const candidatesRef = useRef(candidates);
  candidatesRef.current = candidates;
  const lastRunId = useRef<string | null>(null);
  const autoPlayed = useRef(false);

  // First time the diagram is in view: ONE illustrative pass (never under reduced motion, never over a live run).
  useEffect(() => {
    if (!inView || autoPlayed.current) return;
    autoPlayed.current = true;
    if (!reduce && runId === null) setPass(0);
  }, [inView, reduce, runId]);

  // The illustrative pass advances every PASS_STAGE_MS and then stops.
  useEffect(() => {
    if (pass === null) return;
    const timer = setTimeout(() => setPass(nextStage(pass)), PASS_STAGE_MS);
    return () => clearTimeout(timer);
  }, [pass]);

  // A live run wins over the pass; when it ends successfully all five show done for a moment, then rest.
  useEffect(() => {
    if (runId !== null) {
      lastRunId.current = runId;
      setPass(null);
      setFinishing(false);
      return;
    }
    const ended = lastRunId.current;
    lastRunId.current = null;
    if (ended === null) return;
    if (candidatesRef.current.find((c) => c.id === ended)?.status !== "done") return;
    setFinishing(true);
    const timer = setTimeout(() => setFinishing(false), FINISH_HOLD_MS);
    return () => clearTimeout(timer);
  }, [runId]);

  const view = run
    ? { active: run.stage, done: run.stage, illustrative: false }
    : finishing
      ? { active: null, done: STAGES.length, illustrative: false }
      : pass !== null
        ? { active: pass, done: pass, illustrative: true }
        : { active: null, done: 0, illustrative: false };
  const { active, done, illustrative } = view;

  // Verbs rotate only while a stage is active; reduced motion keeps the first verb.
  useEffect(() => {
    setTick(0);
    if (active === null || reduce) return;
    const timer = setInterval(() => setTick((t) => t + 1), VERB_MS);
    return () => clearInterval(timer);
  }, [active, reduce]);

  const rest = active === null && done === 0;
  const nodeState = (i: number): NodeState => (i === active ? "active" : i < done ? "done" : "rest");
  const connState = (c: number): ConnState =>
    rest ? "rest" : active === c + 1 ? "travelling" : c + 1 < done ? "done" : "upcoming";

  const names = STAGES.map((s) => s.label).join(", ");
  const label =
    `Fluxo em cinco etapas: ${names}. A etapa Skills é inferida pelo modelo; as demais são calculadas por código.` +
    (run ? ` ${stageAnnouncement(run.stage)}.` : "");
  const stage = active !== null ? STAGES[active] : null;
  const busy = run !== null || finishing || pass !== null;

  return (
    <div className="pipeline" ref={root}>
      <div ref={list} className="pipe" role="img" aria-label={label}>
        {STAGES.map((step, i) => (
          <div key={step.id} className="pipe-part">
            {i > 0 && <Connector state={connState(i - 1)} vertical={vertical} reduce={reduce} />}
            <div className="pipe-step">
              <Node step={step} state={nodeState(i)} arrive={i > 0 && !reduce}
                pulse={i === active && !reduce} />
              <span className="pipe-text">
                <span className="pipe-label">{step.label}</span>
                <span className="pipe-caption">{step.caption}</span>
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="pipe-now">
        {stage ? (
          <>
            <span className="pipe-prov">
              <ProvenanceMarker modelo={stage.provenance === "modelo"} />
              {PROVENANCE_TAG[stage.provenance]}
            </span>
            <span className="pipe-verb" aria-hidden="true">
              <AnimatePresence mode="wait" initial={false}>
                <motion.span
                  key={`${active}-${tick}`}
                  style={{ display: "inline-block" }}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.2, ease: "easeOut" }}
                >
                  {verbAt(active as number, tick)}
                </motion.span>
              </AnimatePresence>
            </span>
          </>
        ) : finishing ? (
          <span className="pipe-prov">concluído</span>
        ) : null}
      </div>

      {!reduce && (
        <div className="pipe-tools">
          <span className="pipe-illus">{illustrative ? "passada ilustrativa" : ""}</span>
          <button type="button" className="button button--ghost" disabled={busy} onClick={() => setPass(0)}>
            Reproduzir passada
          </button>
        </div>
      )}

      <p className="pipe-legend" aria-hidden="true">
        <span className="pipe-key"><svg width="18" height="10" viewBox="0 0 18 10"><path d="M0 5h18" /></svg> calculado por código</span>
        <span className="pipe-key"><svg width="18" height="10" viewBox="0 0 18 10"><path d="M0 5h18" strokeDasharray="4 3" /></svg> inferido pelo modelo</span>
      </p>
      <p className="sr-only" aria-live="polite">{run ? stageAnnouncement(run.stage) : ""}</p>
    </div>
  );
}
