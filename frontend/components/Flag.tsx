import type { ReactNode } from "react";

interface Props {
  label: string;
  /** When false there is nothing to flag and nothing is rendered. */
  show?: boolean;
  children: ReactNode;
}

export default function Flag({ label, show = true, children }: Props) {
  if (!show) return null;
  return (
    <div className="flag">
      <span className="flag-k">{label}</span>
      <p>{children}</p>
    </div>
  );
}
