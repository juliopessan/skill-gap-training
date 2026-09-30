"use client";

import { motion, type Variants } from "motion/react";
import { ArrowDownIcon, ArrowUpRightIcon } from "@/components/icons";
import PipelineDiagram from "@/components/PipelineDiagram";
import type { Candidate } from "@/lib/types";

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08, delayChildren: 0.05 } },
};
const item: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" } },
};

const STEPS = [
  { verb: "Extrai", text: "Lê o PDF (com OCR, se for escaneado), remove contatos e pede ao modelo as skills, o nível e a citação." },
  { verb: "Confere", text: "Busca cada citação no texto do CV. Achou: selo. Não achou: alerta com o nome da skill." },
  { verb: "Recomenda", text: "Calcula os gaps contra as trilhas do FY27 (Azure AI Foundry, Microsoft Fabric e Databricks) e sugere treinamentos do catálogo, marcando o que ainda não foi verificado." },
];

interface Props {
  candidates: Candidate[];
  onUpload: () => void;
}

export default function Hero({ candidates, onUpload }: Props) {
  return (
    <motion.section className="hero" variants={container} initial="hidden" animate="show" aria-labelledby="hero-title">
      <div className="hero-copy">
        <motion.p className="eyebrow" variants={item}>Camada de avaliação de skills</motion.p>
        <motion.h1 id="hero-title" className="hero-title" variants={item}>
          <span className="hero-line">Todo gap de skill</span>
          <span className="hero-line voice">é um julgamento.</span>
          <span className="hero-line">Dê a ele evidência.</span>
        </motion.h1>
        <motion.p className="lede" variants={item}>
          O modelo lê o CV e <strong>afirma</strong> níveis. Aqui você vê, ao lado de cada skill, a
          frase do CV que a sustenta — e um alerta quando essa frase não existe.
        </motion.p>
        <div className="meat">
          <ol className="meat-list" aria-label="Como funciona">
            {STEPS.map((step, i) => (
              <motion.li key={step.verb} className="meat-item" variants={item}>
                <span className="meat-num">{String(i + 1).padStart(2, "0")}</span>
                <p><strong>{step.verb}</strong> — {step.text}</p>
              </motion.li>
            ))}
          </ol>
          <motion.p className="meat-close" variants={item}>
            O que foi calculado e o que foi apenas afirmado pelo modelo nunca têm a mesma cara.
          </motion.p>
        </div>
        <motion.div className="cta" variants={item}>
          <div className="cta-row">
            <button type="button" className="button button--solid button--lg" onClick={onUpload}>
              Enviar CVs <ArrowDownIcon />
            </button>
            <a
              className="text-link"
              href="https://github.com/juliopessan/skill-gap-training#como-funciona"
              target="_blank"
              rel="noopener noreferrer"
            >
              Como funciona <ArrowUpRightIcon />
            </a>
          </div>
          <p className="cta-note">
            PDF até 10 MB · até 20 por envio · só o texto do CV vai ao Claude, com contatos removidos
            (melhor esforço)
          </p>
        </motion.div>
      </div>
      <motion.div className="hero-side" variants={item}>
        <p className="eyebrow eyebrow--right">Uma passada completa</p>
        <PipelineDiagram candidates={candidates} />
      </motion.div>
    </motion.section>
  );
}
