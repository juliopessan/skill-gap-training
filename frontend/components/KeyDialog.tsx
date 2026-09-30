"use client";

import { motion } from "motion/react";
import { useEffect, useId, useRef, useState } from "react";
import { CloseIcon } from "@/components/icons";
import {
  keyStatusLabel, removeKey, saveKey, testKey, TEST_MESSAGES, type KeyStatus,
} from "@/lib/settings";

interface Props {
  open: boolean;
  status: KeyStatus | null;
  onClose: () => void;
  onStatus: (status: KeyStatus) => void;
}

type Busy = "save" | "test" | "remove" | null;
interface Message { kind: "info" | "error"; text: string }

export default function KeyDialog({ open, status, onClose, onStatus }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const titleId = useId();
  const hintId = useId();
  const noticeId = useId();
  // The typed key lives only here, and only until the request is sent.
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState<Busy>(null);
  const [message, setMessage] = useState<Message | null>(null);

  useEffect(() => {
    const el = dialog.current;
    if (!el) return;
    if (open && !el.open) {
      el.showModal();
      input.current?.focus();
    } else if (!open && el.open) {
      el.close();
    }
  }, [open]);

  const wipe = () => {
    setValue("");
    if (input.current) input.current.value = "";
  };

  const close = () => {
    wipe();
    setMessage(null);
    onClose();
  };

  const run = async (kind: Exclude<Busy, null>, action: () => Promise<void>) => {
    if (busy) return;
    setBusy(kind);
    setMessage(null);
    try {
      await action();
    } catch (error) {
      setMessage({ kind: "error", text: error instanceof Error ? error.message : "Falha inesperada." });
    } finally {
      setBusy(null);
    }
  };

  const save = () => {
    if (!value.trim()) return;
    void run("save", async () => {
      const pending = saveKey(value);
      wipe(); // the key is on its way; drop it from state and DOM right away
      try {
        onStatus(await pending);
        setMessage({ kind: "info", text: "Chave salva na memória do servidor." });
      } finally {
        wipe();
      }
    });
  };

  const test = () =>
    void run("test", async () => {
      setMessage({ kind: "info", text: TEST_MESSAGES[await testKey()] });
    });

  const remove = () =>
    void run("remove", async () => {
      onStatus(await removeKey());
      setMessage({ kind: "info", text: "Chave da sessão removida." });
    });

  const configured = status?.configured === true;
  const hasSessionKey = status?.source === "session";

  return (
    <dialog
      ref={dialog}
      className="dialog"
      aria-labelledby={titleId}
      onClose={close}
      onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}
    >
      {open && (
        <motion.div
          className="dialog-panel"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
        >
          <div className="dialog-head">
            <p className="eyebrow">Chave da API</p>
            <button type="button" className="icon-button" onClick={close} aria-label="Fechar">
              <CloseIcon />
            </button>
          </div>
          <h2 id={titleId} className="dialog-title">Chave da API da Anthropic</h2>
          <p className="dialog-text">
            A chave fica só na memória do servidor local e some quando a API reinicia. Nunca é
            gravada em arquivo, log ou no navegador.
          </p>

          <div className="field">
            <label className="field-label" htmlFor={`${titleId}-key`}>Chave</label>
            <input
              id={`${titleId}-key`}
              ref={input}
              className="field-input"
              type="password"
              name="skillgap-secret"
              autoComplete="off"
              autoCapitalize="off"
              autoCorrect="off"
              spellCheck={false}
              data-1p-ignore
              data-lpignore="true"
              data-form-type="other"
              placeholder="sk-ant-…"
              value={value}
              disabled={busy !== null}
              aria-describedby={message ? `${hintId} ${noticeId}` : hintId}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") { e.preventDefault(); save(); }
              }}
            />
            <p id={hintId} className="field-hint">
              Estado atual: <span className="mono-inline">{keyStatusLabel(status)}</span>
            </p>
            {status?.source === "environment" && (
              <p className="field-hint">Remover não desativa a chave do ambiente: a API continua usando essa chave.</p>
            )}
          </div>

          <div
            id={noticeId}
            className="dialog-notice-slot"
            role={message?.kind === "error" ? "alert" : "status"}
            aria-live="polite"
          >
            {message && (
              <div className="notice">
                <span className="notice-k">{message.kind === "error" ? "Falha" : "Aviso"}</span>
                <p>{message.text}</p>
              </div>
            )}
          </div>

          <div className="dialog-actions">
            <button type="button" className="button" onClick={test} disabled={busy !== null || !configured}>
              {busy === "test" ? "Testando…" : "Testar"}
            </button>
            <button type="button" className="button button--solid" onClick={save} disabled={busy !== null || !value.trim()}>
              {busy === "save" ? "Salvando…" : "Salvar"}
            </button>
            <button type="button" className="button" onClick={remove} disabled={busy !== null || !hasSessionKey}>
              {busy === "remove" ? "Removendo…" : "Remover"}
            </button>
            <button type="button" className="button" onClick={close}>Fechar</button>
          </div>
        </motion.div>
      )}
    </dialog>
  );
}
