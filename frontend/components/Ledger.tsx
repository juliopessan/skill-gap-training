import { barPercent, fmtHours, pad2, type LedgerFigures } from "@/lib/ledger";

interface Props {
  candidateId: string;
  figures: LedgerFigures;
}

export default function Ledger({ candidateId, figures }: Props) {
  const pct = barPercent(figures.verified, figures.cited);
  return (
    <div className="ledger">
      <div className="ledger-head">
        <span className={`live ${figures.checked ? "" : "live--off"}`}>Ledger do candidato</span>
        <span className="meta">ID {candidateId.slice(0, 8)}</span>
      </div>

      {figures.checked ? (
        <>
          <div className="bar-row">
            <div className="bar-label"><span>Citações do modelo</span><b>{figures.cited}</b></div>
            <div className="bar-track"><div className="bar-fill bar-fill--produced" style={{ width: "100%" }} /></div>
          </div>
          <div className="bar-row">
            <div className="bar-label"><span>Citações localizadas no CV</span><b>{figures.verified}</b></div>
            <div className="bar-track"><div className="bar-fill bar-fill--found" style={{ width: `${pct}%` }} /></div>
          </div>
          {figures.unchecked > 0 && (
            <p className="ledger-note">{figures.unchecked} {figures.unchecked === 1 ? "citação sem verificação" : "citações sem verificação"}</p>
          )}
        </>
      ) : (
        <p className="ledger-note">
          Citações deste registro não foram verificadas (processado antes da verificação).
        </p>
      )}

      <div className="figs">
        <div className="fig"><b>{pad2(figures.gapsHigh)}</b><span>gaps altos</span></div>
        <div className="fig"><b>{pad2(figures.gapsMedium)}</b><span>gaps médios</span></div>
        <div className="fig"><b>{pad2(figures.gapsLow)}</b><span>gaps baixos</span></div>
        <div className="fig"><b>{pad2(figures.coursesTotal)}</b><span>treinamentos</span></div>
        <div className="fig"><b>{fmtHours(figures.hoursTotal)}</b><span>horas de curso</span></div>
        <div className="fig"><b>{pad2(figures.noDataTracks.length)}</b><span>trilhas sem dados</span></div>
      </div>

      {figures.checked && (
        <div className="measured">
          <span className="tick" aria-hidden="true">✓</span>
          <p>
            <span className="k">Calculado, não estimado</span>
            Calculado a partir do CV enviado e dos arquivos de configuração: a busca de cada citação
            no texto do CV e o casamento dos nomes com a taxonomia. A conta dos gaps e o ranking dos
            treinamentos usam os níveis inferidos pelo modelo, que não são medidos. Reconfira com{" "}
            <code>python -m skillgap.cli process &lt;pasta&gt;</code> e compare o JSON.
          </p>
        </div>
      )}
    </div>
  );
}
