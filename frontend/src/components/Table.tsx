import { useState } from "react";
import { pileCards } from "../cards";
import type { GameState, Pile } from "../types";
import { CardChip } from "./CardChip";
import { Sheet } from "./Sheet";

interface Props {
  state: GameState;
  highlight: "deck" | Pile | null;
}

const Stamp = () => <span className="stamp absolute -top-2 right-1 z-10 bg-sheet">best</span>;

export function Table({ state, highlight }: Props) {
  const [open, setOpen] = useState<Pile | null>(null);

  return (
    <section className="grid grid-cols-3 gap-3" aria-label="Table">
      <div className="relative flex flex-col items-center justify-end gap-1">
        {highlight === "deck" && <Stamp />}
        <div className="relative h-28 w-20" aria-hidden="true">
          {/* a stack of face-down sheets */}
          <div className="paper absolute inset-0 translate-x-1 translate-y-1" />
          <div className="paper absolute inset-0 translate-x-0.5 translate-y-0.5" />
          <div className="paper absolute inset-0 grid place-items-center bg-[repeating-linear-gradient(45deg,#E9E1D0_0_6px,#F3EDE1_6px_12px)]">
            <span className="rounded-[2px] bg-sheet px-2 font-serif text-3xl font-bold">{state.deck_count}</span>
          </div>
        </div>
        <span className="text-xs font-semibold text-ink-soft">Deck</span>
      </div>
      {(["a", "b"] as Pile[]).map((p) => {
        const cards = pileCards(state, p);
        const top = cards.at(-1);
        return (
          <button
            key={p}
            type="button"
            onClick={() => setOpen(p)}
            aria-label={`Discard pile ${p.toUpperCase()}, ${cards.length} cards. Show all`}
            className="relative flex flex-col items-center justify-end gap-1"
          >
            {highlight === p && <Stamp />}
            {top ? <CardChip key={top.id} card={top} size="lg" /> : (
              <div className="grid h-28 w-20 place-items-center rounded-[3px] border-2 border-dashed border-crease text-xs text-ink-soft">empty</div>
            )}
            <span className="text-xs font-semibold text-ink-soft">Pile {p.toUpperCase()} · {cards.length}</span>
          </button>
        );
      })}
      {open && (
        <Sheet title={`Pile ${open.toUpperCase()}, top first`} onClose={() => setOpen(null)}>
          <div className="flex flex-wrap gap-2">
            {[...pileCards(state, open)].reverse().map((c) => <CardChip key={c.id} card={c} />)}
          </div>
        </Sheet>
      )}
    </section>
  );
}
