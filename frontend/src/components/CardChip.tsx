import { EMOJI, LABEL, SWATCH } from "../cards";
import type { Card } from "../types";

interface Props {
  card: Card;
  onClick?: () => void;
  selected?: boolean;
  size?: "sm" | "lg";
}

export function CardChip({ card, onClick, selected, size = "sm" }: Props) {
  const big = size === "lg";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      aria-label={`${LABEL[card.name]} ${card.color.replace("_", " ")}`}
      className={`relative flex flex-col items-center justify-center rounded-xl bg-white/95 text-slate-900 shadow
        ${big ? "h-24 w-16 text-3xl" : "h-14 w-11 text-xl"}
        ${selected ? "ring-4 ring-amber-400" : ""} ${onClick ? "active:scale-95" : ""}`}
    >
      <span>{EMOJI[card.name]}</span>
      {big && <span className="mt-1 text-[10px] font-semibold leading-none">{LABEL[card.name]}</span>}
      <span
        className="absolute bottom-0 left-0 right-0 h-1.5 rounded-b-xl"
        style={{ background: SWATCH[card.color], outline: card.color === "white" ? "1px solid #cbd5e1" : undefined }}
      />
    </button>
  );
}
