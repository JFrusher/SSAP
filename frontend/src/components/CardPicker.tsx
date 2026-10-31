import { useState } from "react";
import { CARD_NAMES, COLORS, EMOJI, LABEL, SWATCH, colorLabel, newCard } from "../cards";
import type { Card, CardName } from "../types";
import { Sheet } from "./Sheet";

interface Props {
  title: string;
  remaining: Record<CardName, number>;
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
              disabled={remaining[n] <= 0}
              onClick={() => chooseName(n)}
              className="flex h-20 flex-col items-center justify-center rounded-2xl bg-white/10 active:bg-white/25 disabled:opacity-25"
            >
              <span className="text-3xl">{EMOJI[n]}</span>
              <span className="mt-1 text-[11px] leading-tight">{LABEL[n]}</span>
              <span className="text-[10px] text-sky-300">{remaining[n]} left</span>
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
                className="flex h-20 flex-col items-center justify-center gap-1 rounded-2xl bg-white/10 active:bg-white/25"
              >
                <span className="h-9 w-9 rounded-full border-2 border-white/40" style={{ background: SWATCH[c] }} />
                <span className="text-[10px] capitalize">{colorLabel(c)}</span>
              </button>
            ))}
          </div>
          <button type="button" onClick={() => setName(null)} className="mt-3 w-full py-3 text-sky-300">
            ← Back to card types
          </button>
        </>
      )}
    </Sheet>
  );
}
