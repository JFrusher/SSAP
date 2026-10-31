import type { PlayerState, Recommendation } from "../types";
import { CardChip } from "./CardChip";

const byName = <T extends { name: string }>(a: T, b: T) => a.name.localeCompare(b.name);

export function Hand({ hero, rec }: { hero: PlayerState; rec: Recommendation | null }) {
  return (
    <section className="rounded-2xl bg-white/5 p-3">
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="font-bold">Your hand <span className="text-sm font-normal text-white/50">({hero.hand_size})</span></h2>
        {rec && (
          <span className="text-sm">
            <b className="text-2xl text-amber-300">{rec.hero_points}</b> pts · colour +{rec.hero_color_bonus}
          </span>
        )}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {hero.known_hand.length === 0 && <span className="text-sm text-white/40">No cards yet</span>}
        {[...hero.known_hand].sort(byName).map((c) => <CardChip key={c.id} card={c} />)}
      </div>
      {hero.played_duos.length > 0 && (
        <>
          <h3 className="mb-1 mt-3 text-xs uppercase tracking-wide text-white/50">Played duos</h3>
          <div className="flex flex-wrap gap-1.5 opacity-80">
            {hero.played_duos.map((c) => <CardChip key={c.id} card={c} />)}
          </div>
        </>
      )}
    </section>
  );
}
