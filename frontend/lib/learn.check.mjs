// Runtime check for lib/learn.ts (no extra dependencies): compiles it with the project's own tsc into a temp dir.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
const say = (...parts) => process.stdout.write(parts.join(" ") + "\n");

const here = dirname(fileURLToPath(import.meta.url));
const out = mkdtempSync(join(tmpdir(), "learn-check-"));
execFileSync("npx", ["tsc", join(here, "learn.ts"), "--outDir", out, "--module", "nodenext",
  "--target", "es2022", "--lib", "es2022,dom", "--skipLibCheck", "--types", "node"],
  { stdio: "inherit", cwd: join(here, "..") });
const { kindLabel, certificationsLast, linkLabel, learnSourceLine, isLearnUrl } =
  await import(pathToFileURL(join(out, "learn.js")).href);

assert.equal(kindLabel("certification"), "certificação"); assert.equal(kindLabel("Trilha"), "trilha");
assert.equal(kindLabel("exame"), "exame"); assert.equal(kindLabel(null), ""); assert.equal(kindLabel("outro"), "outro");
assert.deepEqual(certificationsLast([{id:1,kind:"certificação"},{id:2,kind:"curso"},{id:3,kind:"exame"},{id:4}]).map(x=>x.id), [2,4,1,3]);
assert.deepEqual(certificationsLast([]), []);
assert.equal(linkLabel("certificação"), "Abrir certificação →"); assert.equal(linkLabel("exame"), "Abrir exame →");
assert.equal(linkLabel("trilha"), "Abrir trilha →"); assert.equal(linkLabel(undefined), "Abrir curso →");
assert.equal(learnSourceLine({match_origin:"rule", synced_at:"2026-09-30"}), "Microsoft Learn · sincronizado em 30/09/2026 · skills casadas por regra");
assert.equal(learnSourceLine({match_origin:"rule"}), "Microsoft Learn · skills casadas por regra");
assert.equal(learnSourceLine({match_origin:"manual", synced_at:"2026-09-30"}), ""); assert.equal(learnSourceLine({}), "");
for (const ok of ["https://learn.microsoft.com/a"]) assert.equal(isLearnUrl(ok), true);
for (const bad of ["http://learn.microsoft.com/a","https://learn.microsoft.com.evil.com/a","https://evil.com","https://u:p@learn.microsoft.com/a","javascript:1","",null,5]) assert.equal(isLearnUrl(bad), false);
say("ok learn helpers");
