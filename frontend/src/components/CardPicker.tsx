import { useState } from "react";
import { CARD_NAMES, COLORS, LABEL, colorLabel, newCard, type Remaining } from "../cards";
import type { Card, CardName } from "../types";
import { CardArt } from "./CardArt";
import { Sheet } from "./Sheet";

interface Props {
  title: string;
  remaining: Remaining;
  only?: CardName[];
  onPick: (card: Card) => void;
  onClose: () => void;
}

/** Two taps: card type, then colour (mermaids are always white, so one tap). */
export function CardPicker({ title, remaining, only, onPick, onClose }: Props) {
  const [name, setName] = useState<CardName | null>(null);
  const names = only ?? CARD_NAMES;

  const chooseName = (n: CardName) => (n === "mermaid" ? onPick(newCard(n, "white")) : setName(n));

  return (
    <Sheet title={name ? `${LABEL[name]}: which colour?` : title} onClose={onClose}>
      {!name && (
        <div className="grid grid-cols-4 gap-2">
          {names.map((n) => (
            <button
              key={n}
              type="button"
              disabled={remaining.names[n] <= 0}
              onClick={() => chooseName(n)}
              className="paper flex h-[92px] flex-col items-center justify-center gap-0.5 px-1 active:translate-y-px disabled:opacity-30"
            >
              <CardArt name={n} color={null} className="h-10 w-10" />
              <span className="text-center text-[12px] font-semibold leading-tight">{LABEL[n]}</span>
              <span className="text-[11px] text-ink-soft">{remaining.names[n]} left</span>
            </button>
          ))}
        </div>
      )}
      {name && (
        <>
          <div className="grid grid-cols-5 gap-2">
            {COLORS.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => onPick(newCard(name, c))}
                disabled={remaining.colors[c] <= 0}
                className="paper flex h-[96px] flex-col items-center justify-center gap-0.5 px-0.5 active:translate-y-px disabled:opacity-30"
              >
                <CardArt name={name} color={c} className="h-11 w-11" />
                <span className="text-center text-[11px] capitalize leading-tight">{colorLabel(c)}</span>
                <span className="text-[10px] text-ink-soft">{remaining.colors[c]} left</span>
              </button>
            ))}
          </div>
          <button type="button" onClick={() => setName(null)} className="mt-3 min-h-11 w-full font-semibold text-navy underline underline-offset-4">
            Back to card types
          </button>
        </>
      )}
    </Sheet>
  );
}
