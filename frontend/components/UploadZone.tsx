"use client";

import { useRef, useState } from "react";

interface Props {
  onFiles: (files: File[]) => void;
}

export default function UploadZone({ onFiles }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  const pick = (list: FileList | null) => {
    if (list && list.length > 0) onFiles(Array.from(list));
  };

  return (
    <div
      className={`upload ${over ? "upload--over" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files); }}
      onClick={() => input.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          input.current?.click();
        }
      }}
    >
      <input
        ref={input} type="file" accept="application/pdf,.pdf" multiple hidden
        onChange={(e) => { pick(e.target.files); e.target.value = ""; }}
      />
      <strong>Arraste os mini CVs em PDF aqui</strong>
      <span>ou clique para escolher. O restante acontece sozinho.</span>
    </div>
  );
}
