// Runtime check for lib/ledger.ts (no extra dependencies): compiles the module with the
// project's own tsc into a temp dir and runs plain assertions.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const out = mkdtempSync(join(tmpdir(), "ledger-check-"));
execFileSync("npx", ["tsc", join(here, "ledger.ts"), "--outDir", out, "--module", "nodenext",
  "--target", "es2022", "--lib", "es2022,dom", "--skipLibCheck", "--types", "node"],
  { stdio: "inherit", cwd: join(here, "..") });
const { computeLedger, pad2, fmtHours, barPercent } = await import(pathToFileURL(join(out, "ledger.js")).href);

const sk = (id, v) => ({ id, name: id.toUpperCase(), track: "t", level: 2, evidence: "q", ...(v === undefined ? {} : { evidence_verified: v }) });
const ot = (name, v) => ({ name, level: 1, evidence: "q", ...(v === undefined ? {} : { evidence_verified: v }) });
const base = { id: "abcdef123456", candidate: "X", status: "done", stage: "done", error: null,
  error_message: null, no_data_tracks: [], skills: [], other_skills: [], gaps: [], recommendations: [] };

// (a) legacy: all null/absent
let f = computeLedger({ ...base, skills: [sk("a"), sk("b", null)], other_skills: [ot("Go")] });
assert.equal(f.checked, false); assert.equal(f.verified, 0); assert.deepEqual(f.unverifiedNames, []);
assert.equal(f.cited, 3); assert.equal(f.mapped, 2);
console.log("ok (a) legacy record -> checked=false, verified=0");

// (b) all true
f = computeLedger({ ...base, skills: [sk("a", true), sk("b", true)], other_skills: [ot("Go", true)] });
assert.equal(f.checked, true); assert.equal(f.verified, 3); assert.equal(f.cited, 3); assert.deepEqual(f.unverifiedNames, []);
console.log("ok (b) all verified");

// (c) mixed, mapped first, stable order
f = computeLedger({ ...base, skills: [sk("a", false), sk("b", true), sk("c", false)], other_skills: [ot("Zed", false), ot("Go", true), ot("Old")] });
assert.equal(f.checked, true); assert.equal(f.verified, 2);
assert.deepEqual(f.unverifiedNames, ["A", "C", "Zed"]);
console.log("ok (c) mixed -> unverifiedNames in order", JSON.stringify(f.unverifiedNames));

// (d) no gaps; (e) hours summed and gap counts
f = computeLedger(base);
assert.deepEqual([f.gapsHigh, f.gapsMedium, f.gapsLow, f.coursesTotal, f.hoursTotal], [0, 0, 0, 0, 0]);
console.log("ok (d) no gaps");
const gap = (severity) => ({ skill: "s", name: "S", track: "t", expected: 3, current: 1, severity });
f = computeLedger({ ...base, no_data_tracks: ["fabric", "databricks"],
  gaps: [gap("high"), gap("high"), gap("medium"), gap("low")],
  recommendations: [{ course_id: "1", title: "a", covers: [], hours: 8, link: "" }, { course_id: "2", title: "b", covers: [], hours: 12.5, link: "" }] });
assert.deepEqual([f.gapsHigh, f.gapsMedium, f.gapsLow], [2, 1, 1]);
assert.equal(f.coursesTotal, 2); assert.equal(f.hoursTotal, 20.5);
assert.deepEqual(f.noDataTracks, ["fabric", "databricks"]);
console.log("ok (e) hours summed, gap counts, noDataTracks");

// (f) pad2
assert.equal(pad2(3), "03"); assert.equal(pad2(12), "12"); assert.equal(pad2(0), "00");
console.log("ok (f) pad2");

// (g) empty candidate
f = computeLedger(base);
assert.equal(f.checked, false); assert.equal(f.cited, 0); assert.equal(f.verified, 0); assert.equal(f.mapped, 0);
console.log("ok (g) empty candidate");

// (h) unchecked count / partial nulls
f = computeLedger({ ...base, skills: [sk("a", true), sk("b", null), sk("c", false)], other_skills: [ot("Go")] });
assert.equal(f.checked, true); assert.equal(f.unchecked, 2); assert.equal(f.verified, 1); assert.equal(f.cited, 4);
assert.equal(computeLedger({ ...base, skills: [sk("a")] }).unchecked, 1);
assert.equal(computeLedger({ ...base, skills: [sk("a", true)] }).unchecked, 0);
console.log("ok (h) unchecked count with partial nulls");

// (i) duplicate unverified names deduplicated, first occurrence order kept
f = computeLedger({ ...base, skills: [sk("a", false), sk("b", false)], other_skills: [ot("A", false), ot("Zed", false), ot("Zed", false)] });
assert.deepEqual(f.unverifiedNames, ["A", "B", "Zed"]);
console.log("ok (i) duplicate names deduplicated", JSON.stringify(f.unverifiedNames));

// (j) fractional hours rounded to one decimal; fmtHours
f = computeLedger({ ...base, recommendations: [0.1, 0.2, 8.04].map((h, i) => ({ course_id: String(i), title: "t", covers: [], hours: h, link: "" })) });
assert.equal(f.hoursTotal, 8.3);
assert.equal(fmtHours(8), "08"); assert.equal(fmtHours(12.5), "12.5"); assert.equal(fmtHours(8.3), "8.3");
console.log("ok (j) fractional hours rounded and formatted");

// (k) barPercent: both bars share `cited` as basis
assert.equal(barPercent(1, 4), 25); assert.equal(barPercent(0, 0), 0);
assert.equal(barPercent(4, 4), 100); assert.equal(barPercent(5, 4), 100); assert.equal(barPercent(0, 4), 0);
console.log("ok (k) barPercent 1/4=25, 0/0=0, 4/4=100, capped");
assert.equal(fmtHours(8.04), "08");
console.log("ok (l) fmtHours rounds per-course values like the total");
