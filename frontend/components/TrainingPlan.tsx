"use client";

import { useEffect, useId, useMemo, useState } from "react";
import { fmtHours, hasHours } from "@/lib/ledger";
import { certificationsLast, kindLabel, learnSourceLine, linkLabel } from "@/lib/learn";
import { buildSchedule, groupByLevel, LEVEL_LABEL, nextMonday, type CadenceWeeks } from "@/lib/schedule";
import type { Recommendation } from "@/lib/types";

const CADENCES: { value: CadenceWeeks; label: string }[] = [
  { value: 1, label: "1 treinamento a cada 1 semana" },
  { value: 2, label: "1 treinamento a cada 2 semanas" },
  { value: 4, label: "1 treinamento a cada 4 semanas" },
];

function isHttpUrl(value: string): boolean {
  return /^https?:\/\//i.test(value);
}

interface Props {
  recommendations: Recommendation[];
  trackName: (id: string) => string;
  skillName: (id: string) => string;
}

/** Stages by level + a suggested schedule computed in the browser from the user's own inputs. Nothing is stored. */
export default function TrainingPlan({ recommendations, trackName, skillName }: Props) {
  const uid = useId();
  // Empty on the server and on first render (no SSR mismatch); the default is filled after mount.
  const [start, setStart] = useState("");
  const [cadence, setCadence] = useState<CadenceWeeks>(2);
  useEffect(() => { setStart(nextMonday(new Date())); }, []);

  const ordered = useMemo(() => certificationsLast(recommendations), [recommendations]);
  const stages = useMemo(() => groupByLevel(ordered), [ordered]);
  const slots = useMemo(() => buildSchedule(recommendations.length, start, cadence), [recommendations.length, start, cadence]);

  return (
    <div className="plan">
      <div className="plan-controls">
        <div className="plan-field">
          <label className="field-label" htmlFor={`${uid}-start`}>Início</label>
          <input id={`${uid}-start`} className="plan-input" type="date" value={start}
            onChange={(e) => setStart(e.target.value)} />
        </div>
        <div className="plan-field">
          <label className="field-label" htmlFor={`${uid}-cadence`}>Cadência</label>
          <select id={`${uid}-cadence`} className="plan-input" value={cadence}
            onChange={(e) => setCadence(Number(e.target.value) as CadenceWeeks)}>
            {CADENCES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
        </div>
      </div>
      <p className="plan-caption">
        Datas calculadas pela cadência que você escolheu, não pela carga horária, que é desconhecida.
        É um plano sugerido, não um prazo.
      </p>
      <p className="plan-caption plan-caption--order">
        Ordem do cronograma: nível primeiro, depois a prioridade por cobertura de gaps.
      </p>

      {stages.map((stage) => (
        <section key={stage.title} className="stage" aria-label={stage.title}>
          <h4 className="stage-title">{stage.title}</h4>
          <ol className="courses" start={stage.items[0].number}>
            {stage.items.map(({ item: r, number }) => {
              const slot = slots[number - 1];
              const level = r.level != null ? LEVEL_LABEL[r.level] : undefined;
              return (
                <li key={r.course_id}>
                  <div className="course-head">
                    <div className="course-title">{r.title}</div>
                    {slot && (
                      <div className="course-when">
                        <span className="course-range">{slot.range}</span>
                        <span className="course-week">Semana {slot.week}</span>
                      </div>
                    )}
                  </div>
                  <div className="course-meta">
                    {r.provider && <>{r.provider} · </>}
                    {r.kind && <>{kindLabel(r.kind)} · </>}
                    {level && <>{level} · </>}
                    {r.platform && <>{trackName(r.platform)} · </>}
                    {hasHours(r.hours)
                      ? <>{fmtHours(r.hours)} h</>
                      : <span className="course-hours--unknown">horas não informadas</span>}
                    {" · "}
                    {r.exam_codes && r.exam_codes.length > 0 && <>exame {r.exam_codes.join(", ")} · </>}
                    cobre: {r.covers.map(skillName).join(", ")}
                  </div>
                  {learnSourceLine(r) && <div className="course-source">{learnSourceLine(r)}</div>}
                  {isHttpUrl(r.link) && (
                    <a className="course-link" href={r.link} target="_blank" rel="noopener noreferrer">
                      {linkLabel(r.kind)}
                    </a>
                  )}
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </div>
  );
}
