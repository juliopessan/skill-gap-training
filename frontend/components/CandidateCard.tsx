import Flag from "@/components/Flag";
import Ledger from "@/components/Ledger";
import { exportUrl } from "@/lib/api";
import { computeLedger, fmtHours } from "@/lib/ledger";
import type { Candidate, Track } from "@/lib/types";

const LEVEL = ["—", "Básico", "Intermediário", "Avançado"];
const SEVERITY = { high: "Alta", medium: "Média", low: "Baixa" } as const;

function isHttpUrl(value: string): boolean {
  return /^https?:\/\//i.test(value);
}

function joinCodes(names: string[]) {
  return names.map((n, i) => (
    <span key={`${n}-${i}`}>{i > 0 && ", "}<code>{n}</code></span>
  ));
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
        <div className="notice">
          <span className="notice-k">Não processado</span>
          <p>{candidate.error_message ?? "Erro desconhecido."} Corrija a causa e envie o CV de novo.</p>
        </div>
      </section>
    );
  }
  if (candidate.status === "processing") {
    return (
      <section className="card">
        <h2>{candidate.candidate}</h2>
        <p className="caption">Processando…</p>
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
  const figures = computeLedger(candidate);

  return (
    <section className="card">
      <header className="card__header">
        <h2>{candidate.candidate}</h2>
        <div className="actions">
          <a className="button" href={exportUrl(candidate.id, "csv")}>Exportar CSV</a>
          <a className="button" href={exportUrl(candidate.id, "xlsx")}>Exportar XLSX</a>
        </div>
      </header>

      <p className="lede">
        Os níveis são inferidos pelo modelo; cabe a você <span className="voice">confirmar</span> as
        citações antes de agir sobre os gaps.
      </p>

      <Ledger candidateId={candidate.id} figures={figures} />

      {(figures.unverifiedNames.length > 0 || figures.noDataTracks.length > 0) && (
      <div className="flags">
        <Flag label="Citação não encontrada" show={figures.unverifiedNames.length > 0}>
          O texto do CV não contém a citação de: {joinCodes(figures.unverifiedNames)}. Trate o nível
          dessas skills, e os gaps que dependem delas, como não verificados.
        </Flag>
        <Flag label="Sem dados" show={figures.noDataTracks.length > 0}>
          Nenhuma evidência nas trilhas {joinCodes(figures.noDataTracks.map(trackName))}. Não há gaps
          calculados para elas; isso não significa que a pessoa não tenha a skill.
        </Flag>
      </div>
      )}

      <div className="section">
        <p className="eyebrow">01 Skills</p>
        {groups.map((track) => {
          const skills = candidate.skills.filter((s) => s.track === track.id);
          return (
            <div key={track.id} className="track">
              <h4>{track.name}</h4>
              {candidate.no_data_tracks.includes(track.id) ? (
                <p className="caption">Sem dados nesta trilha.</p>
              ) : (
                <ul className="skills">
                  {skills.map((s) => (
                    <li key={s.id} className="skill">
                      <div className="skill-head">
                        <span className="skill-name">{s.name}</span>
                        <span className="skill-level">{LEVEL[s.level]} · {s.level}/3</span>
                        {s.evidence_verified === true && (
                          <span className="skill-tag skill-tag--ok">✓ citação no CV</span>
                        )}
                        {s.evidence_verified === false && (
                          <span className="skill-tag skill-tag--no">citação não encontrada</span>
                        )}
                      </div>
                      <blockquote>{s.evidence}</blockquote>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
        {candidate.other_skills.length > 0 && (
          <div className="others">
            <p className="caption">Outras skills (fora da taxonomia FY27):</p>
            <ul className="others-list">
              {candidate.other_skills.map((o, i) => (
                <li key={`${o.name}-${i}`}>
                  <span className="skill-name">{o.name}</span>{" "}
                  <span className="skill-level">{LEVEL[o.level]}</span>
                  {o.evidence_verified === true && (
                    <span className="skill-tag skill-tag--ok"> ✓ citação no CV</span>
                  )}
                  {o.evidence_verified === false && (
                    <span className="skill-tag skill-tag--no"> citação não encontrada</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="section">
        <p className="eyebrow">02 Gaps</p>
        {candidate.gaps.length === 0 ? (
          <p className="caption">Nenhum gap nas trilhas em que há evidência.</p>
        ) : (
          <div className="tbl-wrap">
            <table>
              <thead>
                <tr>
                  <th>Skill</th><th>Trilha</th>
                  <th className="num">Atual</th><th className="num">Esperado</th><th>Severidade</th>
                </tr>
              </thead>
              <tbody>
                {candidate.gaps.map((g) => (
                  <tr key={g.skill}>
                    <td>{g.name}</td>
                    <td>{trackName(g.track)}</td>
                    <td className="num">{g.current}</td>
                    <td className="num">{g.expected}</td>
                    <td><span className={`sev sev-${g.severity}`}>{SEVERITY[g.severity]}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="section">
        <p className="eyebrow">03 Treinamentos</p>
        {candidate.recommendations.length === 0 ? (
          <p className="caption">Nenhum treinamento do catálogo cobre os gaps encontrados.</p>
        ) : (
          <ol className="courses">
            {candidate.recommendations.map((r) => (
              <li key={r.course_id}>
                <div className="course-title">{r.title}</div>
                <div className="course-meta">{fmtHours(r.hours)} h · cobre: {r.covers.map(skillName).join(", ")}</div>
                {isHttpUrl(r.link) && (
                  <a className="course-link" href={r.link} target="_blank" rel="noopener noreferrer">
                    Abrir curso →
                  </a>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
