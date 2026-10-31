import { X } from "lucide-react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

interface Props {
  title: string;
  onClose: () => void;
  children: ReactNode;
}

/** Bottom sheet that unfolds like paper. Portalled so blurred ancestors can't trap its fixed positioning. */
export function Sheet({ title, onClose, children }: Props) {
  return createPortal(
    <div className="fixed inset-0 z-40 flex flex-col justify-end bg-ink/40" onClick={onClose}>
      <div
        role="dialog"
        aria-label={title}
        className="anim-unfold max-h-[88vh] overflow-y-auto rounded-t-[4px] border-t border-crease bg-sheet p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] text-ink shadow-[0_-10px_30px_-12px_rgba(31,29,26,0.45)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-crease" />
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="font-serif text-xl font-bold leading-tight">{title}</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="grid h-11 w-11 shrink-0 place-items-center rounded-full active:bg-crease/60">
            <X size={22} />
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  );
}

const TONES = {
  default: "bg-sheet text-ink",
  primary: "bg-navy text-white",
  danger: "bg-vermilion text-white",
  good: "bg-sea text-white",
};

export function BigButton({ children, onClick, tone = "default", disabled }: {
  children: ReactNode;
  onClick: () => void;
  tone?: keyof typeof TONES;
  disabled?: boolean;
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} className={`btn-print ${TONES[tone]}`}>
      {children}
    </button>
  );
}
