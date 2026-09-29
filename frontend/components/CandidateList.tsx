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
  if (candidates.length === 0) return <p className="muted">Nenhum CV processado ainda.</p>;
  return (
    <ul className="list">
      {candidates.map((c) => (
        <li key={c.id}>
          <button
            className={`list__item ${c.id === selectedId ? "list__item--active" : ""}`}
            onClick={() => onSelect(c.id)}
          >
            <span className="list__name">{c.candidate || "Sem nome"}</span>
            <span className={`badge badge--${c.status}`}>
              {c.status === "processing" ? STAGES[c.stage] ?? c.stage : STAGES[c.status]}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
