"use client";

import { useState } from "react";
import { BrandMark, KeyIcon } from "@/components/icons";
import { keyStatusLabel, keyStatusWord, type KeyStatus } from "@/lib/settings";

interface Props {
  keyStatus: KeyStatus | null;
  onOpenKey: () => void;
  /** A candidate is processing: the brand mark runs its wave loop. */
  busy?: boolean;
}

export default function AppHeader({ keyStatus, onOpenKey, busy = false }: Props) {
  const [replay, setReplay] = useState(0);
  const again = () => setReplay((n) => n + 1);
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <div className="brand" onMouseEnter={again} onFocus={again}>
          <BrandMark className="brand-mark" animated busy={busy} replayKey={replay} />
          <span className="brand-name">Skill Gap Training</span>
        </div>
        <div className="topbar-right">
          <span className="pill">V1.0 / FY27 · 3 TRILHAS</span>
          <button
            type="button"
            className="button button--solid key-button"
            onClick={onOpenKey}
            aria-haspopup="dialog"
            aria-label={`Chave da API: ${keyStatusLabel(keyStatus)}`}
          >
            <KeyIcon />
            <span className="key-label">Chave da API</span>
            <span className="key-status">{keyStatusWord(keyStatus)}</span>
          </button>
        </div>
      </div>
    </header>
  );
}
