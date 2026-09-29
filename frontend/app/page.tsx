"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import CandidateCard from "@/components/CandidateCard";
import CandidateList from "@/components/CandidateList";
import UploadZone from "@/components/UploadZone";
import { getTracks, listCandidates, uploadCvs } from "@/lib/api";
import type { Candidate, Track } from "@/lib/types";

export default function Home() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const tracksLoaded = useRef(false);

  const refresh = useCallback(async () => {
    try {
      setCandidates(await listCandidates());
      setApiError(null);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Falha ao falar com a API.");
      return;
    }
    if (!tracksLoaded.current) {
      try {
        setTracks(await getTracks());
        tracksLoaded.current = true;
      } catch {
        // tenta de novo no próximo ciclo
      }
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const processing = candidates.some((c) => c.status === "processing");
  const needsRetry = processing || apiError !== null || tracks.length === 0;
  useEffect(() => {
    if (!needsRetry) return;
    const timer = setInterval(refresh, 1500);
    return () => clearInterval(timer);
  }, [needsRetry, refresh]);

  const onFiles = async (files: File[]) => {
    setUploadError(null);
    try {
      const accepted = await uploadCvs(files);
      if (accepted.length > 0) setSelectedId(accepted[0].id);
      await refresh();
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Falha no upload.");
    }
  };

  const selected = candidates.find((c) => c.id === selectedId) ?? null;

  return (
    <main className="page">
      <h1>Skill Gap Training</h1>
      <p className="muted">
        Suba o mini CV e o pipeline faz o resto: extrai skills, calcula os gaps do FY27
        (Azure AI Foundry, Microsoft Fabric e Databricks) e recomenda treinamentos.
      </p>
      <UploadZone onFiles={onFiles} />
      {uploadError && (
        <p className="error" role="alert">
          {uploadError}{" "}
          <button type="button" className="button" onClick={() => setUploadError(null)}>Fechar</button>
        </p>
      )}
      {apiError && <p className="error" role="alert">{apiError}</p>}
      <div className="layout">
        <aside>
          <CandidateList candidates={candidates} selectedId={selectedId} onSelect={setSelectedId} />
        </aside>
        <div>
          {selected ? (
            <CandidateCard candidate={selected} tracks={tracks} />
          ) : (
            <p className="muted">Selecione um candidato para ver o cartão.</p>
          )}
        </div>
      </div>
    </main>
  );
}
