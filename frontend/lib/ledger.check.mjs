// Runtime check for lib/ledger.ts (no extra dependencies): compiles the module with the
// project's own tsc into a temp dir and runs plain assertions.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
const say = (...parts) => process.stdout.write(parts.join(" ") + "\n");

const here = dirname(fileURLToPath(import.meta.url));
const out = mkdtempSync(join(tmpdir(), "ledger-check-"));
execFileSync("npx", ["tsc", join(here, "ledger.ts"), "--outDir", out, "--module", "nodenext",
  "--target", "es2022", "--lib", "es2022,dom", "--skipLibCheck", "--types", "node"],
  { stdio: "inherit", cwd: join(here, "..") });
const { computeLedger, pad2, fmtHours, barPercent, hasHours, formatPercent, ratingView } = await import(pathToFileURL(join(out, "ledger.js")).href);

const sk = (id, v) => ({ id, name: id.toUpperCase(), track: "t", level: 2, evidence: "q", ...(v === undefined ? {} : { evidence_verified: v }) });
const ot = (name, v) => ({ name, level: 1, evidence: "q", ...(v === undefined ? {} : { evidence_verified: v }) });
const base = { id: "abcdef123456", candidate: "X", status: "done", stage: "done", error: null,
  error_message: null, no_data_tracks: [], skills: [], other_skills: [], gaps: [], recommendations: [] };

// (a) legacy: all null/absent
let f = computeLedger({ ...base, skills: [sk("a"), sk("b", null)], other_skills: [ot("Go")] });
assert.equal(f.checked, false); assert.equal(f.verified, 0); assert.deepEqual(f.unverifiedNames, []);
assert.equal(f.cited, 3); assert.equal(f.mapped, 2);
say("ok (a) legacy record -> checked=false, verified=0");

// (b) all true
f = computeLedger({ ...base, skills: [sk("a", true), sk("b", true)], other_skills: [ot("Go", true)] });
assert.equal(f.checked, true); assert.equal(f.verified, 3); assert.equal(f.cited, 3); assert.deepEqual(f.unverifiedNames, []);
say("ok (b) all verified");

// (c) mixed, mapped first, stable order
f = computeLedger({ ...base, skills: [sk("a", false), sk("b", true), sk("c", false)], other_skills: [ot("Zed", false), ot("Go", true), ot("Old")] });
assert.equal(f.checked, true); assert.equal(f.verified, 2);
assert.deepEqual(f.unverifiedNames, ["A", "C", "Zed"]);
say("ok (c) mixed -> unverifiedNames in order", JSON.stringify(f.unverifiedNames));

// (d) no gaps; (e) hours summed and gap counts
f = computeLedger(base);
assert.deepEqual([f.gapsHigh, f.gapsMedium, f.gapsLow, f.coursesTotal, f.hoursTotal], [0, 0, 0, 0, 0]);
say("ok (d) no gaps");
const gap = (severity) => ({ skill: "s", name: "S", track: "t", expected: 3, current: 1, severity });
f = computeLedger({ ...base, no_data_tracks: ["fabric", "databricks"],
  gaps: [gap("high"), gap("high"), gap("medium"), gap("low")],
  recommendations: [{ course_id: "1", title: "a", covers: [], hours: 8, link: "" }, { course_id: "2", title: "b", covers: [], hours: 12.5, link: "" }] });
assert.deepEqual([f.gapsHigh, f.gapsMedium, f.gapsLow], [2, 1, 1]);
assert.equal(f.coursesTotal, 2); assert.equal(f.hoursTotal, 20.5);
assert.deepEqual(f.noDataTracks, ["fabric", "databricks"]);
say("ok (e) hours summed, gap counts, noDataTracks");

// (f) pad2
assert.equal(pad2(3), "03"); assert.equal(pad2(12), "12"); assert.equal(pad2(0), "00");
say("ok (f) pad2");

// (g) empty candidate
f = computeLedger(base);
assert.equal(f.checked, false); assert.equal(f.cited, 0); assert.equal(f.verified, 0); assert.equal(f.mapped, 0);
say("ok (g) empty candidate");

// (h) unchecked count / partial nulls
f = computeLedger({ ...base, skills: [sk("a", true), sk("b", null), sk("c", false)], other_skills: [ot("Go")] });
assert.equal(f.checked, true); assert.equal(f.unchecked, 2); assert.equal(f.verified, 1); assert.equal(f.cited, 4);
assert.equal(computeLedger({ ...base, skills: [sk("a")] }).unchecked, 1);
assert.equal(computeLedger({ ...base, skills: [sk("a", true)] }).unchecked, 0);
say("ok (h) unchecked count with partial nulls");

// (i) duplicate unverified names deduplicated, first occurrence order kept
f = computeLedger({ ...base, skills: [sk("a", false), sk("b", false)], other_skills: [ot("A", false), ot("Zed", false), ot("Zed", false)] });
assert.deepEqual(f.unverifiedNames, ["A", "B", "Zed"]);
say("ok (i) duplicate names deduplicated", JSON.stringify(f.unverifiedNames));

// (j) fractional hours rounded to one decimal; fmtHours
f = computeLedger({ ...base, recommendations: [0.1, 0.2, 8.04].map((h, i) => ({ course_id: String(i), title: "t", covers: [], hours: h, link: "" })) });
assert.equal(f.hoursTotal, 8.3);
assert.equal(fmtHours(8), "08"); assert.equal(fmtHours(12.5), "12.5"); assert.equal(fmtHours(8.3), "8.3");
say("ok (j) fractional hours rounded and formatted");

// (k) barPercent: both bars share `cited` as basis
assert.equal(barPercent(1, 4), 25); assert.equal(barPercent(0, 0), 0);
assert.equal(barPercent(4, 4), 100); assert.equal(barPercent(5, 4), 100); assert.equal(barPercent(0, 4), 0);
say("ok (k) barPercent 1/4=25, 0/0=0, 4/4=100, capped");
assert.equal(fmtHours(8.04), "08");
say("ok (l) fmtHours rounds per-course values like the total");

// (m) hours: none known, mixed, all known; hoursUnknown counts null/missing
const rec = (id, hours, extra = {}) => ({ course_id: id, title: id, covers: [], hours, link: "", ...extra });
f = computeLedger({ ...base, recommendations: [rec("a", null), rec("b", null)] });
assert.equal(f.coursesTotal, 2); assert.equal(f.hoursTotal, 0); assert.equal(f.hoursUnknown, 2);
f = computeLedger({ ...base, recommendations: [rec("a", 8), rec("b", null), rec("c", 12.5), rec("d", undefined)] });
assert.equal(f.hoursTotal, 20.5); assert.equal(f.hoursUnknown, 2); assert.equal(f.coursesTotal, 4);
f = computeLedger({ ...base, recommendations: [rec("a", 8), rec("b", 2)] });
assert.equal(f.hoursTotal, 10); assert.equal(f.hoursUnknown, 0);
f = computeLedger(base);
assert.equal(f.hoursTotal, 0); assert.equal(f.hoursUnknown, 0);
assert.equal(hasHours(null), false); assert.equal(hasHours(NaN), false); assert.equal(hasHours(0), true);
say("ok (m) hours: all null, mixed, none, all known");

// (n) unverified catalogue: only verified === false is listed; missing/null/true are not
f = computeLedger({ ...base, recommendations: [rec("a", 1, { verified: false }), rec("b", 1, { verified: true }),
  rec("c", 1, { verified: null }), rec("d", 1), rec("e", null, { verified: false })] });
assert.deepEqual(f.unverifiedCourses, ["a", "e"]);
f = computeLedger({ ...base, recommendations: [rec("b", 1, { verified: true }), rec("c", 1, { verified: null }), rec("d", 1)] });
assert.deepEqual(f.unverifiedCourses, []);
say("ok (n) unverifiedCourses only for verified === false");

// (o) the catalogue flag names courses by TITLE, not course_id
f = computeLedger({ ...base, recommendations: [
  { course_id: "c-9", title: "Fabric Analytics Engineer", covers: [], hours: 4, link: "", verified: false },
  { course_id: "c-7", title: "Databricks Fundamentals", covers: [], hours: null, link: "", verified: false }] });
assert.deepEqual(f.unverifiedCourses, ["Fabric Analytics Engineer", "Databricks Fundamentals"]);
say("ok (o) unverifiedCourses lists titles");

// (p) formatPercent: pt-BR decimal comma, one decimal, rounding
assert.equal(formatPercent(72.5), "72,5%"); assert.equal(formatPercent(0), "0,0%");
assert.equal(formatPercent(100), "100,0%"); assert.equal(formatPercent(61), "61,0%");
assert.equal(formatPercent(72.54), "72,5%"); assert.equal(formatPercent(72.56), "72,6%");
assert.equal(formatPercent(NaN), "—"); assert.equal(formatPercent(Infinity), "—");
say("ok (p) formatPercent comma decimals, rounding, non-finite");

// (q) ratingView: missing/null -> null (nothing rendered)
assert.equal(ratingView(undefined), null); assert.equal(ratingView(null), null);
assert.equal(ratingView({ adherence: "x" }), null);
assert.equal(computeLedger(base).noDataTracks.length, 0);
say("ok (q) missing rating -> null");

// (r) ratingView: supported never displayed above adherence; clamped; tracks keep API order
const tr = (track, adherence, label) => ({ track, name: track.toUpperCase(), adherence, adherence_supported: adherence,
  covered: 1, expected: 2, skills_rated: 3, mean_level: 2, level_label: label });
let v = ratingView({ adherence: 60, adherence_supported: 75, covered: 6, expected: 10, mean_level: 2.1,
  level_label: "Intermediário", tracks: [tr("fabric", 64.4, "Intermediário"), tr("azure", 40, null), tr("databricks", 120, "Avançado")] });
assert.equal(v.adherence, 60); assert.equal(v.supported, 60); assert.equal(v.levelLabel, "Intermediário");
assert.deepEqual(v.tracks.map((t) => t.track), ["fabric", "azure", "databricks"]);
assert.deepEqual(v.tracks.map((t) => t.text), ["Intermediário · 64%", "40%", "Avançado · 100%"]);
assert.equal(v.tracks[2].percent, 100);
v = ratingView({ adherence: 72.5, adherence_supported: 61, covered: 1, expected: 2, mean_level: null, level_label: null, tracks: [] });
assert.equal(v.supported, 61); assert.equal(v.levelLabel, null); assert.deepEqual(v.tracks, []);
say("ok (r) supported <= adherence, clamp, per-track order/text");
