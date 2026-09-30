"use client";

import { useRef, useState, type Ref } from "react";
import { UploadIcon } from "@/components/icons";

interface Props {
  onFiles: (files: File[]) => void;
  ref?: Ref<HTMLDivElement>;
}

export default function UploadZone({ onFiles, ref }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  const pick = (list: FileList | null) => {
    if (list && list.length > 0) onFiles(Array.from(list));
  };

  return (
    <div
      ref={ref}
      id="upload"
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
      <UploadIcon className="upload-icon" size={20} />
      <strong>Arraste os mini CVs em PDF aqui</strong>
      <span>ou clique para escolher. O restante acontece sozinho.</span>
    </div>
  );
}
