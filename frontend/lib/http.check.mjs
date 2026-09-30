// Runtime check for lib/http.ts (no extra dependencies): compiles the helper with the
// project's own tsc into a temp dir and exercises it with stubbed fetch.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
const say = (...parts) => process.stdout.write(parts.join(" ") + "\n");

const here = dirname(fileURLToPath(import.meta.url));
const out = mkdtempSync(join(tmpdir(), "http-check-"));
execFileSync("npx", ["tsc", join(here, "http.ts"), "--outDir", out, "--module", "nodenext",
  "--target", "es2022", "--lib", "es2022,dom", "--skipLibCheck", "--types", "node"],
  { stdio: "inherit", cwd: join(here, "..") });
const { request, json } = await import(pathToFileURL(join(out, "http.js")).href);

// (a) successful stub is really called once with url/init and its Response is returned
const calls = [];
const ok = new Response("{}", { status: 200 });
const got = await request("http://x/y", { method: "POST" }, async (...a) => { calls.push(a); return ok; }, "http://x");
assert.equal(calls.length, 1);
assert.deepEqual(calls[0], ["http://x/y", { method: "POST" }]);
assert.equal(got, ok);
say("ok (a) fetch called once and Response returned");

// (b) network failure -> Portuguese message
await assert.rejects(
  request("http://x/y", undefined, async () => { throw new TypeError("Failed to fetch"); }, "http://base:1"),
  { message: "Não consegui falar com a API. Ela está rodando em http://base:1?" });
say("ok (b) TypeError('Failed to fetch') -> mensagem em português");

// (c) json() error handling
await assert.rejects(json(new Response(JSON.stringify({ detail: "texto" }), { status: 413 })), { message: "texto" });
await assert.rejects(json(new Response(JSON.stringify({ detail: [{ msg: "x" }] }), { status: 422 })), { message: "Erro 422" });
assert.deepEqual(await json(new Response('{"a":1}', { status: 200 })), { a: 1 });
say("ok (c) json(): string detail, non-string detail, success");
