import { X } from "lucide-react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

interface Props {
  title: string;
  onClose: () => void;
  children: ReactNode;
}

/** Bottom sheet: thumb-reachable on phones. Portalled so blurred ancestors can't trap its fixed positioning. */
export function Sheet({ title, onClose, children }: Props) {
  return createPortal(
    <div className="fixed inset-0 z-40 flex flex-col justify-end bg-black/60" onClick={onClose}>
      <div
        className="max-h-[88vh] overflow-y-auto rounded-t-3xl bg-slate-900 p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] text-white"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-bold">{title}</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="rounded-full p-2 active:bg-white/10">
            <X size={22} />
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  );
}

export function BigButton({ children, onClick, tone = "default", disabled }: {
  children: ReactNode;
  onClick: () => void;
  tone?: "default" | "primary" | "danger" | "good";
  disabled?: boolean;
}) {
  const tones = {
    default: "bg-white/10 active:bg-white/20",
    primary: "bg-sky-500 active:bg-sky-600 text-slate-950",
    danger: "bg-rose-500 active:bg-rose-600 text-white",
    good: "bg-emerald-500 active:bg-emerald-600 text-slate-950",
  };
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`flex min-h-14 w-full items-center justify-center gap-2 rounded-2xl px-4 text-base font-semibold disabled:opacity-40 ${tones[tone]}`}
    >
      {children}
    </button>
  );
}
