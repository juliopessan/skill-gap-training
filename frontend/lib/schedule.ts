// Pure schedule helpers. All date arithmetic is done on UTC calendar parts (Date.UTC), never on
// local time, so DST transitions cannot shift a day: results are identical in every time zone.

export const LEVEL_LABEL: Record<number, string> = { 1: "Básico", 2: "Intermediário", 3: "Avançado" };
export const NO_LEVEL_TITLE = "Sem nível informado";
export type CadenceWeeks = 1 | 2 | 4;

export interface Stage<T> {
  /** 1-3, or null for the "no level" group. */
  level: 1 | 2 | 3 | null;
  title: string;
  /** Items in API order, each with its sequence number (continues across stages, starts at 1). */
  items: { item: T; number: number }[];
}

const isLevel = (n: unknown): n is 1 | 2 | 3 => n === 1 || n === 2 || n === 3;

/** Stages by level (only levels present, ascending) plus a final "Sem nível informado" group. */
export function groupByLevel<T extends { level?: number | null }>(items: readonly T[]): Stage<T>[] {
  const buckets = new Map<1 | 2 | 3 | null, T[]>();
  for (const item of items) {
    const key = isLevel(item.level) ? item.level : null;
    const list = buckets.get(key);
    if (list) list.push(item); else buckets.set(key, [item]);
  }
  const stages: Stage<T>[] = [];
  let number = 0;
  let stageNo = 0;
  for (const key of [1, 2, 3, null] as const) {
    const list = buckets.get(key);
    if (!list) continue;
    // Stages are numbered sequentially over the groups actually present; "no level" has no number.
    stages.push({
      level: key,
      title: key === null ? NO_LEVEL_TITLE : `Etapa ${++stageNo} · ${LEVEL_LABEL[key]}`,
      items: list.map((item) => ({ item, number: ++number })),
    });
  }
  return stages;
}

export interface Slot {
  /** 1-based week number since the start date. */
  week: number;
  startISO: string;
  endISO: string;
  /** "dd/mm – dd/mm" */
  range: string;
}

const ISO = /^(\d{4})-(\d{2})-(\d{2})$/;

/** Parses "YYYY-MM-DD" into a UTC-midnight timestamp; null for empty/invalid/impossible dates. */
export function parseISODate(value: string | null | undefined): number | null {
  const m = typeof value === "string" ? ISO.exec(value) : null;
  if (!m) return null;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const t = Date.UTC(y, mo - 1, d);
  const back = new Date(t);
  if (back.getUTCFullYear() !== y || back.getUTCMonth() !== mo - 1 || back.getUTCDate() !== d) return null;
  return t;
}

const DAY = 86_400_000;
const two = (n: number) => String(n).padStart(2, "0");
const toISO = (t: number) => {
  const d = new Date(t);
  return `${d.getUTCFullYear()}-${two(d.getUTCMonth() + 1)}-${two(d.getUTCDate())}`;
};

/** "dd/mm – dd/mm" from two ISO dates; "" when either is invalid. */
export function formatRange(startISO: string, endISO: string): string {
  const a = parseISODate(startISO);
  const b = parseISODate(endISO);
  if (a === null || b === null) return "";
  const f = (t: number) => `${two(new Date(t).getUTCDate())}/${two(new Date(t).getUTCMonth() + 1)}`;
  return `${f(a)} – ${f(b)}`;
}

/**
 * Item k (0-based, in schedule order) starts at start + k * cadence * 7 days and ends
 * cadence * 7 - 1 days later. Empty/invalid start (or count 0) -> []: only the stages are shown.
 */
export function buildSchedule(count: number, startISO: string, cadenceWeeks: CadenceWeeks): Slot[] {
  const start = parseISODate(startISO);
  if (start === null || !Number.isInteger(count) || count <= 0) return [];
  if (cadenceWeeks !== 1 && cadenceWeeks !== 2 && cadenceWeeks !== 4) return [];
  const span = cadenceWeeks * 7;
  return Array.from({ length: count }, (_, k) => {
    const s = start + k * span * DAY;
    const e = s + (span - 1) * DAY;
    return { week: k * cadenceWeeks + 1, startISO: toISO(s), endISO: toISO(e), range: formatRange(toISO(s), toISO(e)) };
  });
}

/** The Monday strictly after `today` (a Monday gives the following one), as "YYYY-MM-DD".
 *  Uses the local calendar date of `today`, then UTC arithmetic. */
export function nextMonday(today: Date): string {
  const base = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  const dow = new Date(base).getUTCDay(); // 0 Sun .. 6 Sat
  const add = ((8 - dow) % 7) || 7;
  return toISO(base + add * DAY);
}
