import { ArrowUpRightIcon, BrandMark } from "@/components/icons";

const LINKS = [
  { label: "Como funciona", href: "https://github.com/juliopessan/skill-gap-training#como-funciona" },
  { label: "Repositório", href: "https://github.com/juliopessan/skill-gap-training" },
];

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <div className="brand">
            <BrandMark className="brand-mark" />
            <span className="brand-name">SKILL GAP TRAINING</span>
          </div>
          <p className="footer-version">V1.0 / FY27</p>
        </div>
        <nav className="footer-links" aria-label="Links do projeto">
          {LINKS.map((l) => (
            <a key={l.href} className="text-link" href={l.href} target="_blank" rel="noopener noreferrer">
              {l.label} <ArrowUpRightIcon />
            </a>
          ))}
        </nav>
        <div className="footer-notes">
          <p>Só o texto do CV vai ao Claude, com contatos removidos (melhor esforço).</p>
          <p>A chave da API fica só na memória do servidor local.</p>
          <p>Itens da Microsoft Learn vêm do catálogo oficial (nível, duração e link); a lista manual segue não verificada: confirme na fonte.</p>
          <p className="footer-scope">Ferramenta local, de uso individual</p>
        </div>
      </div>
    </footer>
  );
}
