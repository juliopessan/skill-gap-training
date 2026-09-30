// Pure helpers for Microsoft Learn items. No project imports: the check compiles this file alone.

interface KindLike { kind?: string | null }
interface SourceLike { match_origin?: string | null; synced_at?: string | null }

const KIND_LABEL: Record<string, string> = {
  course: "curso", curso: "curso", trilha: "trilha",
  certification: "certificação", certificacao: "certificação", "certificação": "certificação",
  exam: "exame", exame: "exame",
};

export function kindLabel(kind: string | null | undefined): string {
  if (!kind) return "";
  return KIND_LABEL[kind.toLowerCase()] ?? kind;
}

const isMilestone = (kind: string | null | undefined) => {
  const k = kindLabel(kind);
  return k === "certificação" || k === "exame";
};

/** Stable partition: courses/trilhas first, certifications/exams last (groupByLevel then keeps this order inside each stage). */
export function certificationsLast<T extends KindLike>(items: readonly T[]): T[] {
  return [...items.filter((i) => !isMilestone(i.kind)), ...items.filter((i) => isMilestone(i.kind))];
}

export function linkLabel(kind: string | null | undefined): string {
  switch (kindLabel(kind)) {
    case "certificação": return "Abrir certificação →";
    case "exame": return "Abrir exame →";
    case "trilha": return "Abrir trilha →";
    default: return "Abrir curso →";
  }
}

function formatSynced(value: string | null | undefined): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value ?? "");
  return m ? `${m[3]}/${m[2]}/${m[1]}` : "";
}

/** "" for manual/old records. The skill link is a code rule, never shown as "verified". */
export function learnSourceLine(r: SourceLike): string {
  if (r.match_origin !== "rule") return "";
  const date = formatSynced(r.synced_at);
  return `Microsoft Learn${date ? ` · sincronizado em ${date}` : ""} · skills casadas por regra`;
}

export function isLearnUrl(value: unknown): boolean {
  if (typeof value !== "string") return false;
  try {
    const u = new URL(value);
    return u.protocol === "https:" && u.hostname === "learn.microsoft.com" && !u.username && !u.password;
  } catch {
    return false;
  }
}
