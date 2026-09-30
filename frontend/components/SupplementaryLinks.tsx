import { isLearnUrl } from "@/lib/learn";
import type { SupplementaryItem } from "@/lib/types";

interface Props {
  items?: SupplementaryItem[] | null;
  status?: string | null;
  skillName: (id: string) => string;
}

/** Documentation links from the Microsoft Learn search. Not courses, no level. Only learn.microsoft.com links render. */
export default function SupplementaryLinks({ items, status, skillName }: Props) {
  const safe = (items ?? []).filter((i) => isLearnUrl(i.url));
  if (safe.length === 0) {
    return status === "unavailable"
      ? <p className="plan-caption">Busca complementar da Microsoft Learn indisponível agora. As recomendações acima não dependem dela.</p>
      : null;
  }
  return (
    <section className="supp" aria-label="Leitura complementar">
      <h4 className="stage-title">Leitura complementar</h4>
      <p className="plan-caption">
        Encontrado pela busca da Microsoft Learn para gaps sem item no catálogo. Não é curso e não tem nível.
      </p>
      <ul className="supp-list">
        {safe.map((i) => (
          <li key={i.url}>
            <a className="course-link" href={i.url} target="_blank" rel="noopener noreferrer">{i.title} →</a>
            <span className="course-meta"> · {skillName(i.skill)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
