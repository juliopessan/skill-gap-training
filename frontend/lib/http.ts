export const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function request(
  url: string,
  init?: RequestInit,
  fetchImpl: typeof fetch = (input, init) => fetch(input, init),
  base: string = BASE,
): Promise<Response> {
  try {
    return await fetchImpl(url, init);
  } catch {
    throw new Error(`Não consegui falar com a API. Ela está rodando em ${base}?`);
  }
}

export async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(
      typeof detail?.detail === "string" ? detail.detail : `Erro ${response.status}`,
    );
  }
  return response.json() as Promise<T>;
}
