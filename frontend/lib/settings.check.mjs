// Runtime check for lib/settings.ts (no extra dependencies): compiles it (and http.ts) with the
// project's own tsc into a temp dir and exercises it with a stub fetch. Fake key only.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
const say = (...parts) => process.stdout.write(parts.join(" ") + "\n");

const here = dirname(fileURLToPath(import.meta.url));
const out = mkdtempSync(join(tmpdir(), "settings-check-"));
execFileSync("npx", ["tsc", join(here, "settings.ts"), "--outDir", out, "--module", "nodenext",
  "--target", "es2022", "--lib", "es2022,dom", "--skipLibCheck", "--types", "node"],
  { stdio: "inherit", cwd: join(here, "..") });
const { getKeyStatus, saveKey, removeKey, testKey } = await import(pathToFileURL(join(out, "settings.js")).href);

const FAKE = "sk-ant-test-0000000000000000";
const BASE = "http://api.test";
const reply = (body, status = 200) => new Response(JSON.stringify(body), { status });

// (a) PUT: method, header, exact body, key absent from the URL
{
  const calls = [];
  const status = await saveKey(FAKE, async (url, init) => { calls.push([url, init]); return reply({ configured: true, source: "session" }); }, BASE);
  assert.equal(calls.length, 1);
  const [url, init] = calls[0];
  assert.equal(url, `${BASE}/settings/api-key`);
  assert.equal(init.method, "PUT");
  assert.deepEqual(init.headers, { "Content-Type": "application/json" });
  assert.equal(init.body, JSON.stringify({ api_key: FAKE }));
  assert.equal(init.body, `{"api_key":"${FAKE}"}`);
  assert.ok(!url.includes(FAKE) && !url.includes("api_key"));
  assert.deepEqual(status, { configured: true, source: "session" });
  say("ok (a) PUT method, content-type, exact body, key absent from URL");
}

// (b) 422 on save surfaces the Portuguese detail without the key
await assert.rejects(
  saveKey(FAKE, async () => reply({ detail: "A chave é curta demais para ser válida." }, 422), BASE),
  (e) => e.message === "A chave é curta demais para ser válida." && !e.message.includes(FAKE));
say("ok (b) 422 detail is passed through");

// (c) getKeyStatus and removeKey parse the status object
{
  const seen = [];
  const f = async (url, init) => { seen.push([url, init?.method ?? "GET"]); return reply({ configured: false, source: null }); };
  assert.deepEqual(await getKeyStatus(f, BASE), { configured: false, source: null });
  assert.deepEqual(await removeKey(f, BASE), { configured: false, source: null });
  assert.deepEqual(seen, [[`${BASE}/settings/api-key`, "GET"], [`${BASE}/settings/api-key`, "DELETE"]]);
  assert.deepEqual(await getKeyStatus(async () => reply({ configured: true, source: "environment" }), BASE),
    { configured: true, source: "environment" });
  say("ok (c) getKeyStatus / removeKey parse the status");
}

// (d) testKey: each status, POST to /test, 409 -> Portuguese error
{
  for (const s of ["valid", "invalid", "unreachable", "error"]) {
    let seen;
    const got = await testKey(async (url, init) => { seen = [url, init.method]; return reply({ status: s }); }, BASE);
    assert.equal(got, s);
    assert.deepEqual(seen, [`${BASE}/settings/api-key/test`, "POST"]);
  }
  await assert.rejects(testKey(async () => reply({ detail: "Nenhuma chave configurada." }, 409), BASE),
    { message: "Nenhuma chave configurada." });
  say("ok (d) testKey statuses and 409 -> Portuguese message");
}

// (e) network failure -> Portuguese network message
await assert.rejects(
  saveKey(FAKE, async () => { throw new TypeError("Failed to fetch"); }, "http://base:1"),
  { message: "Não consegui falar com a API. Ela está rodando em http://base:1?" });
await assert.rejects(getKeyStatus(async () => { throw new TypeError("x"); }, "http://base:1"),
  { message: "Não consegui falar com a API. Ela está rodando em http://base:1?" });
say("ok (e) network failure -> mensagem em português");

// (f) status labels and test messages
{
  const { keyStatusLabel, keyStatusWord, TEST_MESSAGES } = await import(pathToFileURL(join(out, "settings.js")).href);
  assert.equal(keyStatusLabel(null), "—");
  assert.equal(keyStatusLabel({ configured: false, source: null }), "Ausente");
  assert.equal(keyStatusLabel({ configured: true, source: "session" }), "Configurada (sessão)");
  assert.equal(keyStatusLabel({ configured: true, source: "environment" }), "Configurada (variável de ambiente)");
  assert.deepEqual(
    [null, { configured: false, source: null }, { configured: true, source: "session" }, { configured: true, source: "environment" }]
      .map(keyStatusWord),
    ["—", "AUSENTE", "SESSÃO", "AMBIENTE"]);
  assert.equal(TEST_MESSAGES.valid, "Chave válida.");
  assert.equal(TEST_MESSAGES.unreachable, "Não consegui falar com a API da Anthropic.");
  say("ok (f) status labels and test messages");
}
