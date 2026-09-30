// Runtime check for lib/pipeline.ts (no extra dependencies): compiles it with the project's own tsc.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
const say = (...parts) => process.stdout.write(parts.join(" ") + "\n");

const here = dirname(fileURLToPath(import.meta.url));
const out = mkdtempSync(join(tmpdir(), "pipeline-check-"));
execFileSync("npx", ["tsc", join(here, "pipeline.ts"), "--outDir", out, "--module", "nodenext",
  "--target", "es2022", "--lib", "es2022,dom", "--skipLibCheck", "--types", "node"],
  { stdio: "inherit", cwd: join(here, "..") });
const { STAGES, PROVENANCE_TAG, stageFromBackend, nextStage, verbAt, stageAnnouncement, liveRun } =
  await import(pathToFileURL(join(out, "pipeline.js")).href);

// (a) every backend stage maps to its node; unknown -> null
assert.deepEqual(["queued", "reading", "extracting", "analyzing", "recommending"].map(stageFromBackend), [0, 1, 2, 3, 4]);
for (const bad of ["done", "error", "", "READING", "toString", "__proto__", "constructor"]) {
  assert.equal(stageFromBackend(bad), null, bad);
}
say("ok (a) queued..recommending -> 0..4; done/error/unknown/prototype keys -> null");

// (b) order and labels
assert.deepEqual(STAGES.map((s) => s.label), ["PDF", "Texto", "Skills", "Gaps", "Treinamentos"]);
assert.deepEqual(STAGES.map((s) => s.id), ["pdf", "text", "skills", "gaps", "courses"]);
say("ok (b) stage order PDF, Texto, Skills, Gaps, Treinamentos");

// (c) verbs and provenance
for (const s of STAGES) {
  assert.ok(s.verbs.length >= 3, s.id);
  for (const v of s.verbs) assert.match(v, /^[a-zà-ú].*ndo .*…$/, v); // lowercase gerund phrase, trailing ellipsis
}
assert.deepEqual(STAGES.map((s) => s.provenance), ["codigo", "codigo", "modelo", "codigo", "codigo"]);
assert.equal(PROVENANCE_TAG.codigo, "CALCULADO POR CÓDIGO");
assert.equal(PROVENANCE_TAG.modelo, "INFERIDO PELO MODELO");
assert.deepEqual(STAGES[2].verbs, ["lendo o CV…", "inferindo skills e níveis…", "escolhendo a citação de cada skill…"]);
say("ok (c) >= 3 verbs per stage, provenance codigo/modelo/codigo, tags");

// (d) illustrative pass sequencing ends after the last stage
const seq = [0]; let cur = 0;
while ((cur = nextStage(cur)) !== null) seq.push(cur);
assert.deepEqual(seq, [0, 1, 2, 3, 4]);
assert.equal(nextStage(4), null); assert.equal(nextStage(-1), null); assert.equal(nextStage(1.5), null);
say("ok (d) nextStage 0->1->2->3->4->null");

// (e) verb rotation wraps; announcement names the stage and provenance only
assert.equal(verbAt(0, 0), "recebendo o arquivo…"); assert.equal(verbAt(0, 3), "recebendo o arquivo…");
assert.equal(verbAt(4, 5), "ordenando por nível…");
assert.equal(stageAnnouncement(2), "Etapa atual: Skills, inferido pelo modelo");
assert.equal(stageAnnouncement(3), "Etapa atual: Gaps, calculado por código");
say("ok (e) verb wrap and stage announcement text");

// (f) liveRun: newest processing candidate (first in the list), real stage; none/unknown -> null
const c = (id, status, stage) => ({ id, status, stage });
assert.equal(liveRun([]), null);
assert.equal(liveRun([c("a", "done", "done"), c("b", "error", "error")]), null);
assert.deepEqual(liveRun([c("a", "done", "done"), c("b", "processing", "analyzing"), c("c", "processing", "reading")]), { id: "b", stage: 3 });
assert.equal(liveRun([c("a", "processing", "mystery")]), null);
say("ok (f) liveRun picks the newest processing candidate's real stage");
