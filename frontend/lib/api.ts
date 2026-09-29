import type { Candidate, Track } from "./types";
import { BASE, json, request } from "./http";

export async function uploadCvs(files: File[]): Promise<Candidate[]> {
  const body = new FormData();
  files.forEach((file) => body.append("files", file));
  return json<Candidate[]>(await request(`${BASE}/candidates`, { method: "POST", body }));
}

export async function listCandidates(): Promise<Candidate[]> {
  return json<Candidate[]>(await request(`${BASE}/candidates`, { cache: "no-store" }));
}

export async function getTracks(): Promise<Track[]> {
  const data = await json<{ tracks: Track[] }>(await request(`${BASE}/taxonomy`));
  return data.tracks;
}

export function exportUrl(id: string, format: "csv" | "xlsx"): string {
  return `${BASE}/candidates/${id}/export?format=${format}`;
}
