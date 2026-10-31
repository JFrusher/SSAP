import { LABEL, colorLabel } from "../cards";
import type { Card } from "../types";
import { CardArt } from "./CardArt";

interface Props {
  card: Card;
  onClick?: () => void;
  selected?: boolean;
  size?: "sm" | "lg";
}

/** A folded paper card: the art is drawn in the card's own colour. */
export function CardChip({ card, onClick, selected, size = "sm" }: Props) {
  const big = size === "lg";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      aria-label={`${LABEL[card.name]}, ${colorLabel(card.color)}`}
      className={`paper folded anim-flip flex shrink-0 flex-col items-center justify-center
        ${big ? "h-28 w-20 gap-1 p-1.5" : "h-[60px] w-11 p-1"}
        ${selected ? "border-[3px] border-vermilion" : ""} ${onClick ? "active:translate-y-px" : ""}`}
    >
      <CardArt name={card.name} color={card.color} className={big ? "h-14 w-14" : "h-8 w-8"} />
      {big && <span className="font-serif text-[13px] font-bold leading-none">{LABEL[card.name]}</span>}
    </button>
  );
}
