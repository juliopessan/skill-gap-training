import type { Candidate } from "./types";

export type Provenance = "codigo" | "modelo";

export interface PipelineStage {
  id: "pdf" | "text" | "skills" | "gaps" | "courses";
  label: string;
  caption: string;
  /** codigo = computed by code (solid marker); modelo = inferred by the language model (dashed marker). */
  provenance: Provenance;
  /** Gerund phrases describing what the stage really does; the UI rotates through them. */
  verbs: string[];
}

export const STAGES: PipelineStage[] = [
  { id: "pdf", label: "PDF", caption: "mini CV enviado", provenance: "codigo",
    verbs: ["recebendo o arquivo…", "validando o PDF…", "conferindo o hash do cache…"] },
  { id: "text", label: "Texto", caption: "nativo ou OCR", provenance: "codigo",
    verbs: ["lendo o texto nativo…", "rodando OCR onde precisa…", "removendo contatos…"] },
  { id: "skills", label: "Skills", caption: "inferido pelo modelo", provenance: "modelo",
    verbs: ["lendo o CV…", "inferindo skills e níveis…", "escolhendo a citação de cada skill…"] },
  { id: "gaps", label: "Gaps", caption: "regra calculada", provenance: "codigo",
    verbs: ["procurando cada citação no CV…", "casando nomes com a taxonomia…", "calculando gaps e rating…"] },
  { id: "courses", label: "Treinamentos", caption: "catálogo de cursos", provenance: "codigo",
    verbs: ["consultando o catálogo…", "ranqueando por cobertura…", "ordenando por nível…"] },
];

export const PROVENANCE_TAG: Record<Provenance, string> = {
  codigo: "CALCULADO POR CÓDIGO",
  modelo: "INFERIDO PELO MODELO",
};

/** Timing of the illustrative pass and of the verb rotation, in milliseconds. */
export const PASS_STAGE_MS = 1500;
export const VERB_MS = 1100;
/** How long "all done" stays visible after a live run finishes. */
export const FINISH_HOLD_MS = 1500;

const STAGE_TO_INDEX: Record<string, number> = {
  queued: 0, reading: 1, extracting: 2, analyzing: 3, recommending: 4,
};

/** Backend stage -> index into STAGES; null for unknown (or terminal) stages. */
export function stageFromBackend(stage: string): number | null {
  return Object.prototype.hasOwnProperty.call(STAGE_TO_INDEX, stage) ? STAGE_TO_INDEX[stage] : null;
}

/** Illustrative pass sequencing: the stage after `index`, or null when the pass is over. */
export function nextStage(index: number): number | null {
  return Number.isInteger(index) && index >= 0 && index < STAGES.length - 1 ? index + 1 : null;
}

/** The verb shown at rotation tick `tick` for a stage (wraps around). */
export function verbAt(stageIndex: number, tick: number): string {
  const verbs = STAGES[stageIndex].verbs;
  return verbs[((tick % verbs.length) + verbs.length) % verbs.length];
}

/** Text for the polite live region: announced only when the STAGE changes. */
export function stageAnnouncement(stageIndex: number): string {
  const s = STAGES[stageIndex];
  return `Etapa atual: ${s.label}, ${s.provenance === "modelo" ? "inferido pelo modelo" : "calculado por código"}`;
}

export interface LiveRun { id: string; stage: number }

/** The most recent processing candidate (the API lists newest first) and its real stage. */
export function liveRun(candidates: readonly Candidate[]): LiveRun | null {
  const current = candidates.find((c) => c.status === "processing");
  if (!current) return null;
  const stage = stageFromBackend(current.stage);
  return stage === null ? null : { id: current.id, stage };
}
