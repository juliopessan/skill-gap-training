"use client";

import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import AppHeader from "@/components/AppHeader";
import CandidateCard from "@/components/CandidateCard";
import CandidateList from "@/components/CandidateList";
import Footer from "@/components/Footer";
import Hero from "@/components/Hero";
import KeyDialog from "@/components/KeyDialog";
import UploadZone from "@/components/UploadZone";
import { getTracks, listCandidates, uploadCvs } from "@/lib/api";
import { useBusyFavicon } from "@/lib/useBusyFavicon";
import { getKeyStatus, type KeyStatus } from "@/lib/settings";
import type { Candidate, Track } from "@/lib/types";

export default function Home() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [keyStatus, setKeyStatus] = useState<KeyStatus | null>(null);
  const [keyOpen, setKeyOpen] = useState(false);
  const uploadRef = useRef<HTMLDivElement>(null);
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

  // Status da chave: busca ao montar; se a API estiver fora do ar, tenta de novo até responder.
  useEffect(() => {
    if (keyStatus !== null) return;
    let cancelled = false;
    const load = () =>
      getKeyStatus().then((status) => { if (!cancelled) setKeyStatus(status); }, () => undefined);
    load();
    const timer = setInterval(load, 3000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [keyStatus]);

  const processing = candidates.some((c) => c.status === "processing");
  useBusyFavicon(processing);
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

  const focusUpload = () => {
    const zone = uploadRef.current;
    if (!zone) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    zone.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
    zone.focus({ preventScroll: true });
  };

  const selected = candidates.find((c) => c.id === selectedId) ?? null;

  return (
    <>
    <AppHeader keyStatus={keyStatus} onOpenKey={() => setKeyOpen(true)} busy={processing} />
    <KeyDialog
      open={keyOpen}
      status={keyStatus}
      onClose={() => setKeyOpen(false)}
      onStatus={setKeyStatus}
    />
    <main className="page">
      <Hero candidates={candidates} onUpload={focusUpload} />
      <UploadZone ref={uploadRef} onFiles={onFiles} />
      {uploadError && (
        <div className="notice" role="alert">
          <span className="notice-k">Falha</span>
          <p>{uploadError}</p>
          <button type="button" className="button" onClick={() => setUploadError(null)}>Fechar</button>
        </div>
      )}
      {apiError && (
        <div className="notice" role="alert">
          <span className="notice-k">Falha</span>
          <p>{apiError}</p>
        </div>
      )}
      <div className="layout">
        <aside>
          <CandidateList candidates={candidates} selectedId={selectedId} onSelect={setSelectedId} />
        </aside>
        <div>
          <AnimatePresence mode="wait" initial={false}>
            {selected ? (
              <motion.div
                key={selected.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.25, ease: "easeOut" }}
              >
                <CandidateCard candidate={selected} tracks={tracks} onConfigureKey={() => setKeyOpen(true)} />
              </motion.div>
            ) : (
              <motion.p
                key="empty"
                className="caption"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
              >
                Selecione um candidato para ver o cartão.
              </motion.p>
            )}
          </AnimatePresence>
        </div>
      </div>
    </main>
    <Footer />
    </>
  );
}
