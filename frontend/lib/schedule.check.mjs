// Runtime check for lib/schedule.ts (no extra dependencies): compiles it with the project's own
// tsc into a temp dir. The DST/time-zone cases re-run the module in child processes with TZ set
// BEFORE node starts, and require identical results in every zone.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
const say = (...parts) => process.stdout.write(parts.join(" ") + "\n");

const here = dirname(fileURLToPath(import.meta.url));
const out = mkdtempSync(join(tmpdir(), "schedule-check-"));
execFileSync("npx", ["tsc", join(here, "schedule.ts"), "--outDir", out, "--module", "nodenext",
  "--target", "es2022", "--lib", "es2022,dom", "--skipLibCheck", "--types", "node"],
  { stdio: "inherit", cwd: join(here, "..") });
const modPath = join(out, "schedule.js");
const { groupByLevel, buildSchedule, nextMonday, formatRange, parseISODate } = await import(pathToFileURL(modPath).href);

const it = (id, level) => (level === undefined ? { id } : { id, level });

// (a) grouping: levels ascending, only those present, API order kept inside a stage, no-level last
let stages = groupByLevel([it("a", 3), it("b", 1), it("c", null), it("d", 1), it("e"), it("f", 3), it("g", 2), it("h", 9)]);
assert.deepEqual(stages.map((s) => s.title),
  ["Etapa 1 · Básico", "Etapa 2 · Intermediário", "Etapa 3 · Avançado", "Sem nível informado"]);
assert.deepEqual(stages.map((s) => s.items.map((x) => x.item.id)), [["b", "d"], ["g"], ["a", "f"], ["c", "e", "h"]]);
say("ok (a) grouping by level, API order inside a stage, no-level group last");

// (b) numbering continues across stages, starting at 1
assert.deepEqual(stages.flatMap((s) => s.items.map((x) => x.number)), [1, 2, 3, 4, 5, 6, 7, 8]);
say("ok (b) sequence numbers continue across stages");

// (c) only levels present; all missing; empty
stages = groupByLevel([it("a", 2), it("b", 2)]);
assert.deepEqual(stages.map((s) => [s.level, s.title]), [[2, "Etapa 1 · Intermediário"]]);
stages = groupByLevel([it("a", 3), it("b", 2)]);
assert.deepEqual(stages.map((s) => s.title), ["Etapa 1 · Intermediário", "Etapa 2 · Avançado"]);
stages = groupByLevel([it("a", 3)]);
assert.deepEqual(stages.map((s) => s.title), ["Etapa 1 · Avançado"]);
stages = groupByLevel([it("a", 1), it("b", 2), it("c", 3)]);
assert.deepEqual(stages.map((s) => s.title), ["Etapa 1 · Básico", "Etapa 2 · Intermediário", "Etapa 3 · Avançado"]);
stages = groupByLevel([it("u"), it("a", 3)]);
assert.deepEqual(stages.map((s) => s.title), ["Etapa 1 · Avançado", "Sem nível informado"]);
stages = groupByLevel([it("a"), it("b", null)]);
assert.deepEqual(stages.map((s) => [s.level, s.title]), [[null, "Sem nível informado"]]);
assert.deepEqual(groupByLevel([]), []);
say("ok (c) only present levels, all-missing, empty list");

// (d) cadence math 1/2/4 weeks (2026-03-02 is a Monday)
let s = buildSchedule(3, "2026-03-02", 1);
assert.deepEqual(s.map((x) => x.range), ["02/03 – 08/03", "09/03 – 15/03", "16/03 – 22/03"]);
assert.deepEqual(s.map((x) => x.week), [1, 2, 3]);
s = buildSchedule(3, "2026-03-02", 2);
assert.deepEqual(s.map((x) => x.range), ["02/03 – 15/03", "16/03 – 29/03", "30/03 – 12/04"]);
assert.deepEqual(s.map((x) => x.week), [1, 3, 5]);
s = buildSchedule(3, "2026-03-02", 4);
assert.deepEqual(s.map((x) => x.range), ["02/03 – 29/03", "30/03 – 26/04", "27/04 – 24/05"]);
assert.deepEqual(s.map((x) => x.week), [1, 5, 9]);
assert.equal(s[1].startISO, "2026-03-30"); assert.equal(s[1].endISO, "2026-04-26");
say("ok (d) cadence 1/2/4 weeks: start + k*cadence*7, end = +cadence*7-1");

// (e) month and year rollover, leap day
s = buildSchedule(3, "2026-12-14", 2);
assert.deepEqual(s.map((x) => x.range), ["14/12 – 27/12", "28/12 – 10/01", "11/01 – 24/01"]);
assert.equal(s[1].endISO, "2027-01-10");
s = buildSchedule(2, "2028-02-21", 1);
assert.deepEqual(s.map((x) => x.range), ["21/02 – 27/02", "28/02 – 05/03"]);
s = buildSchedule(1, "2028-02-28", 1);
assert.equal(s[0].endISO, "2028-03-05"); // 2028 is a leap year
say("ok (e) month/year rollover and leap year");

// (f) empty list, invalid or empty date, invalid cadence
assert.deepEqual(buildSchedule(0, "2026-03-02", 2), []);
for (const bad of ["", "2026-13-01", "2026-02-30", "abc", "2026-3-2", null, undefined]) {
  assert.deepEqual(buildSchedule(3, bad, 2), [], String(bad));
}
assert.deepEqual(buildSchedule(3, "2026-03-02", 3), []);
assert.equal(parseISODate("2026-02-29"), null);
assert.equal(formatRange("nope", "2026-03-02"), "");
say("ok (f) empty list / invalid or empty date / bad cadence -> no dates");

// (g) nextMonday: strictly after today, from the LOCAL calendar date
assert.equal(nextMonday(new Date(2026, 8, 29)), "2026-10-05"); // Tuesday
assert.equal(nextMonday(new Date(2026, 2, 30)), "2026-04-06"); // Monday -> the following Monday
assert.equal(nextMonday(new Date(2026, 2, 29, 23, 59)), "2026-03-30"); // Sunday (London DST day)
assert.equal(nextMonday(new Date(2026, 2, 28, 0, 0)), "2026-03-30"); // Saturday
assert.equal(nextMonday(new Date(2026, 11, 31)), "2027-01-04"); // year rollover
say("ok (g) nextMonday");

// (h) DST boundaries: identical results in London, Sao Paulo, Auckland and UTC
const probe = `
const m = require(process.env.SCHEDULE_MOD);
const r = {
  spring: m.buildSchedule(3, "2026-03-25", 1).map((x) => x.range),
  autumn: m.buildSchedule(3, "2026-10-21", 1).map((x) => x.range),
  four: m.buildSchedule(2, "2026-03-02", 4).map((x) => x.range + "|" + x.endISO),
  mondaySpring: m.nextMonday(new Date(2026, 2, 29, 1, 30)),
  mondayAutumn: m.nextMonday(new Date(2026, 9, 25, 1, 30)),
  tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
};
process.stdout.write(JSON.stringify(r));`;
const runIn = (tz) => JSON.parse(execFileSync(process.execPath, ["-e", probe],
  { env: { ...process.env, TZ: tz, SCHEDULE_MOD: modPath }, encoding: "utf8" }));
const zones = ["Europe/London", "America/Sao_Paulo", "Pacific/Auckland", "UTC"];
const results = zones.map(runIn);
results.forEach((r, i) => assert.equal(r.tz, zones[i]));
const strip = ({ tz, ...rest }) => rest;
for (const r of results) assert.deepEqual(strip(r), strip(results[0]));
assert.deepEqual(results[0].spring, ["25/03 – 31/03", "01/04 – 07/04", "08/04 – 14/04"]);
assert.deepEqual(results[0].autumn, ["21/10 – 27/10", "28/10 – 03/11", "04/11 – 10/11"]);
assert.equal(results[0].mondaySpring, "2026-03-30");
assert.equal(results[0].mondayAutumn, "2026-10-26");
say("ok (h) DST (2026-03-29, 2026-10-25) identical across", zones.join(", "));
