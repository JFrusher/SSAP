import { useState } from "react";
import { Layers } from "lucide-react";
import { pileCards } from "../cards";
import type { GameState, Pile } from "../types";
import { CardChip } from "./CardChip";
import { Sheet } from "./Sheet";

interface Props {
  state: GameState;
  highlight: "deck" | Pile | null;
}

export function Table({ state, highlight }: Props) {
  const [open, setOpen] = useState<Pile | null>(null);
  const ring = (k: "deck" | Pile) => (highlight === k ? "ring-2 ring-amber-400" : "");

  return (
    <section className="grid grid-cols-3 gap-2">
      <div className={`flex flex-col items-center justify-center rounded-2xl bg-sky-950/60 p-2 ${ring("deck")}`}>
        <Layers className="text-sky-300" />
        <span className="text-3xl font-bold">{state.deck_count}</span>
        <span className="text-xs text-sky-300">in deck</span>
      </div>
      {(["a", "b"] as Pile[]).map((p) => {
        const cards = pileCards(state, p);
        const top = cards.at(-1);
        return (
          <button
            key={p}
            type="button"
            onClick={() => setOpen(p)}
            className={`flex flex-col items-center gap-1 rounded-2xl bg-sky-950/60 p-2 active:bg-sky-900 ${ring(p)}`}
          >
            {top ? <CardChip card={top} size="lg" /> : <div className="flex h-24 w-16 items-center justify-center rounded-xl border-2 border-dashed border-white/20 text-xs text-white/40">empty</div>}
            <span className="text-xs text-sky-300">Pile {p.toUpperCase()} · {cards.length}</span>
          </button>
        );
      })}
      {open && (
        <Sheet title={`Discard pile ${open.toUpperCase()} (top first)`} onClose={() => setOpen(null)}>
          <div className="flex flex-wrap gap-2">
            {[...pileCards(state, open)].reverse().map((c) => <CardChip key={c.id} card={c} />)}
          </div>
        </Sheet>
      )}
    </section>
  );
}
