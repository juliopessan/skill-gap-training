"use client";

import { motion, useReducedMotion } from "motion/react";
import { CheckIcon } from "@/components/icons";
import CountUp from "@/components/CountUp";
import { barPercent, fmtHours, formatPercent, pad2, ratingView, type LedgerFigures, type RatingView } from "@/lib/ledger";
import type { Rating } from "@/lib/types";

const count = (n: number) => String(Math.round(n));
const padded = (n: number) => pad2(Math.round(n));

function Bar({ className, percent, reduce }: { className: string; percent: number; reduce: boolean }) {
  return (
    <div className="bar-track">
      <motion.div
        className={`bar-fill ${className}`}
        initial={reduce ? false : { width: 0 }}
        animate={{ width: `${percent}%` }}
        transition={{ duration: 0.5, ease: "easeOut", delay: 0.1 }}
      />
    </div>
  );
}

/** Known hours only. Unknown loads are never counted as zero: "—" when none is known, else a caption. */
function HoursFigure({ figures }: { figures: LedgerFigures }) {
  const noneKnown = figures.coursesTotal > 0 && figures.hoursUnknown === figures.coursesTotal;
  if (noneKnown) {
    return (
      <div className="fig">
        <b>—</b>
        <span>horas (não informadas)</span>
      </div>
    );
  }
  return (
    <div className="fig">
      <b><CountUp value={figures.hoursTotal} format={fmtHours} /></b>
      <span>horas de curso</span>
      {figures.hoursUnknown > 0 && (
        <span className="fig-note">+ {figures.hoursUnknown} sem carga horária informada</span>
      )}
    </div>
  );
}

/** Rating FY27: computed by rule from LEVELS INFERRED BY THE MODEL, so it is never marked as measured. */
function RatingBlock({ view, reduce }: { view: RatingView; reduce: boolean }) {
  return (
    <div className="rating">
      <p className="rating-k">Rating FY27</p>
      <div className="rating-head">
        <b className="rating-figure"><CountUp value={view.adherence} format={formatPercent} /></b>
        {view.levelLabel && <span className="rating-level">{view.levelLabel}</span>}
      </div>
      <p className="rating-sub">
        <span>com citação localizada:</span>{" "}
        <b><CountUp value={view.supported} format={formatPercent} /></b>
      </p>
      {view.tracks.length > 0 && (
        <ul className="rating-tracks">
          {view.tracks.map((t) => (
            <li key={t.track} className="rating-track">
              <div className="rating-track-head">
                <span className="rating-track-name">{t.name}</span>
                <span className="rating-track-val">{t.text}</span>
              </div>
              <Bar className="bar-fill--rating" percent={t.percent} reduce={reduce} />
            </li>
          ))}
        </ul>
      )}
      <p className="rating-note">
        Rating calculado por regra sobre níveis inferidos pelo modelo; não é uma medição.
        Aderência: % dos níveis esperados no FY27 atingidos (limitada ao nível esperado), nas trilhas
        com dados. Com citação localizada: mesma conta só com as skills cuja citação foi achada no
        CV, então é um piso.
      </p>
    </div>
  );
}

interface Props {
  candidateId: string;
  figures: LedgerFigures;
  rating?: Rating | null;
}

export default function Ledger({ candidateId, figures, rating }: Props) {
  const reduce = useReducedMotion() ?? false;
  const pct = barPercent(figures.verified, figures.cited);
  const ratingModel = ratingView(rating);
  return (
    <div className="ledger">
      <div className="ledger-head">
        <span className={`live ${figures.checked ? "" : "live--off"}`}>Ledger do candidato</span>
        <span className="meta">ID {candidateId.slice(0, 8)}</span>
      </div>

      {figures.checked ? (
        <>
          <div className="bar-row">
            <div className="bar-label"><span>Citações do modelo</span><b><CountUp value={figures.cited} format={count} /></b></div>
            <Bar className="bar-fill--produced" percent={100} reduce={reduce} />
          </div>
          <div className="bar-row">
            <div className="bar-label"><span>Citações localizadas no CV</span><b><CountUp value={figures.verified} format={count} /></b></div>
            <Bar className="bar-fill--found" percent={pct} reduce={reduce} />
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
        <div className="fig"><b><CountUp value={figures.gapsHigh} format={padded} /></b><span>gaps altos</span></div>
        <div className="fig"><b><CountUp value={figures.gapsMedium} format={padded} /></b><span>gaps médios</span></div>
        <div className="fig"><b><CountUp value={figures.gapsLow} format={padded} /></b><span>gaps baixos</span></div>
        <div className="fig"><b><CountUp value={figures.coursesTotal} format={padded} /></b><span>treinamentos</span></div>
        <HoursFigure figures={figures} />
        <div className="fig"><b><CountUp value={figures.noDataTracks.length} format={padded} /></b><span>trilhas sem dados</span></div>
      </div>

      {ratingModel && <RatingBlock view={ratingModel} reduce={reduce} />}

      {figures.checked && (
        <div className="measured">
          <span className="tick" aria-hidden="true"><CheckIcon draw size={16} strokeWidth={2} /></span>
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
