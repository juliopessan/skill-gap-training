import { exportUrl } from "@/lib/api";
import type { Candidate, Track } from "@/lib/types";

const LEVEL = ["—", "Básico", "Intermediário", "Avançado"];
const SEVERITY = { high: "Alta", medium: "Média", low: "Baixa" } as const;

function isHttpUrl(value: string): boolean {
  return /^https?:\/\//i.test(value);
}

interface Props {
  candidate: Candidate;
  tracks: Track[];
}

export default function CandidateCard({ candidate, tracks }: Props) {
  if (candidate.status === "error") {
    return (
      <section className="card">
        <h2>{candidate.candidate}</h2>
        <p className="error">Não consegui processar este PDF: {candidate.error_message}</p>
      </section>
    );
  }
  if (candidate.status === "processing") {
    return (
      <section className="card">
        <h2>{candidate.candidate}</h2>
        <p className="muted">Processando…</p>
      </section>
    );
  }

  // Sem a lista de trilhas (API fora do ar no carregamento), agrupa pelos ids das próprias skills.
  const groups: Track[] =
    tracks.length > 0
      ? tracks
      : Array.from(new Set(candidate.skills.map((s) => s.track))).map((id) => ({ id, name: id }));
  const trackName = (id: string) => tracks.find((t) => t.id === id)?.name ?? id;
  const skillName = (id: string) =>
    candidate.gaps.find((g) => g.skill === id)?.name ??
    candidate.skills.find((s) => s.id === id)?.name ?? id;

  return (
    <section className="card">
      <header className="card__header">
        <h2>{candidate.candidate}</h2>
        <div className="actions">
          <a className="button" href={exportUrl(candidate.id, "csv")}>Exportar CSV</a>
          <a className="button" href={exportUrl(candidate.id, "xlsx")}>Exportar XLSX</a>
        </div>
      </header>

      <h3>Skills encontradas</h3>
      {groups.map((track) => {
        const skills = candidate.skills.filter((s) => s.track === track.id);
        return (
          <div key={track.id} className="track">
            <h4>{track.name}</h4>
            {candidate.no_data_tracks.includes(track.id) ? (
              <p className="muted">Sem dados nesta trilha.</p>
            ) : (
              <ul>
                {skills.map((s) => (
                  <li key={s.id}>
                    <strong>{s.name}</strong> <span className="pill">{LEVEL[s.level]}</span>
                    <blockquote>{s.evidence}</blockquote>
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
      {candidate.other_skills.length > 0 && (
        <p className="muted">
          Outras skills (fora da taxonomia FY27):{" "}
          {candidate.other_skills.map((o) => `${o.name} (${LEVEL[o.level]})`).join(", ")}
        </p>
      )}

      <h3>Gaps</h3>
      {candidate.gaps.length === 0 ? (
        <p className="muted">Nenhum gap nas trilhas em que há evidência.</p>
      ) : (
        <table>
          <thead>
            <tr><th>Skill</th><th>Trilha</th><th>Atual</th><th>Esperado</th><th>Severidade</th></tr>
          </thead>
          <tbody>
            {candidate.gaps.map((g) => (
              <tr key={g.skill}>
                <td>{g.name}</td>
                <td>{trackName(g.track)}</td>
                <td>{LEVEL[g.current]}</td>
                <td>{LEVEL[g.expected]}</td>
                <td><span className={`sev sev--${g.severity}`}>{SEVERITY[g.severity]}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3>Treinamentos recomendados</h3>
      {candidate.recommendations.length === 0 ? (
        <p className="muted">Nenhum treinamento do catálogo cobre os gaps encontrados.</p>
      ) : (
        <ol className="courses">
          {candidate.recommendations.map((r) => (
            <li key={r.course_id}>
              <strong>{r.title}</strong> <span className="muted">· {r.hours} h</span>
              <div className="muted">Cobre: {r.covers.map(skillName).join(", ")}</div>
              {isHttpUrl(r.link) && (
                <a href={r.link} target="_blank" rel="noopener noreferrer">Abrir curso</a>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
