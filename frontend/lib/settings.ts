import { BASE, json, request } from "./http";

export interface KeyStatus {
  configured: boolean;
  source: "session" | "environment" | null;
}
export type KeyTestResult = "valid" | "invalid" | "unreachable" | "error";

type Fetch = typeof fetch;
const URL_KEY = "/settings/api-key";

export async function getKeyStatus(fetchImpl?: Fetch, base: string = BASE): Promise<KeyStatus> {
  return json<KeyStatus>(await request(`${base}${URL_KEY}`, { cache: "no-store" }, fetchImpl, base));
}

/** The key travels only in the JSON body of this PUT; nothing here keeps a copy. */
export async function saveKey(key: string, fetchImpl?: Fetch, base: string = BASE): Promise<KeyStatus> {
  return json<KeyStatus>(
    await request(
      `${base}${URL_KEY}`,
      { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ api_key: key }) },
      fetchImpl,
      base,
    ),
  );
}

export async function removeKey(fetchImpl?: Fetch, base: string = BASE): Promise<KeyStatus> {
  return json<KeyStatus>(await request(`${base}${URL_KEY}`, { method: "DELETE" }, fetchImpl, base));
}

export async function testKey(fetchImpl?: Fetch, base: string = BASE): Promise<KeyTestResult> {
  const data = await json<{ status: KeyTestResult }>(
    await request(`${base}${URL_KEY}/test`, { method: "POST" }, fetchImpl, base),
  );
  return data.status;
}

/** Long form for the dialog. `null` = status unknown (API down). */
export function keyStatusLabel(status: KeyStatus | null): string {
  if (!status) return "—";
  if (!status.configured) return "Ausente";
  return status.source === "environment" ? "Configurada (variável de ambiente)" : "Configurada (sessão)";
}

/** Short form for the header button. */
export function keyStatusWord(status: KeyStatus | null): string {
  if (!status) return "—";
  if (!status.configured) return "AUSENTE";
  return status.source === "environment" ? "AMBIENTE" : "SESSÃO";
}

export const TEST_MESSAGES: Record<KeyTestResult, string> = {
  valid: "Chave válida.",
  invalid: "Chave inválida.",
  unreachable: "Não consegui falar com a API da Anthropic.",
  error: "Não foi possível testar a chave.",
};
