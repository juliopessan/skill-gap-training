"use client";

import { AnimatePresence, motion } from "motion/react";
import type { Candidate } from "@/lib/types";

const STAGES: Record<string, string> = {
  queued: "Na fila",
  reading: "Lendo PDF",
  extracting: "Extraindo skills",
  analyzing: "Calculando gap",
  recommending: "Recomendando treinamentos",
  done: "Pronto",
  error: "Erro",
};

interface Props {
  candidates: Candidate[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export default function CandidateList({ candidates, selectedId, onSelect }: Props) {
  return (
    <div aria-live="polite">
      {candidates.length === 0 ? (
        <p className="caption">Nenhum CV processado ainda.</p>
      ) : (
        <ul className="list">
          <AnimatePresence initial={false}>
          {candidates.map((c) => (
            <motion.li
              key={c.id}
              layout
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25, ease: "easeOut" }}
            >
              <button
                className={`list__item ${c.id === selectedId ? "list__item--active" : ""}`}
                aria-current={c.id === selectedId ? "true" : undefined}
                onClick={() => onSelect(c.id)}
              >
                <span className="list__name">{c.candidate || "Sem nome"}</span>
                <span className="status">
                  {(c.status === "processing" ? STAGES[c.stage] ?? c.stage : STAGES[c.status] ?? c.status).toUpperCase()}
                </span>
              </button>
            </motion.li>
          ))}
          </AnimatePresence>
        </ul>
      )}
    </div>
  );
}
