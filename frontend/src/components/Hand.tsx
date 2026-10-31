import type { PlayerState, Recommendation } from "../types";
import { CardChip } from "./CardChip";

const byName = <T extends { name: string }>(a: T, b: T) => a.name.localeCompare(b.name);

export function Hand({ hero, rec }: { hero: PlayerState; rec: Recommendation | null }) {
  return (
    <section className="paper p-3" aria-label="Your hand">
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="font-serif text-lg font-bold">Your hand <span className="font-sans text-sm font-normal text-ink-soft">{hero.hand_size} cards</span></h2>
        {rec && (
          <span className="text-sm text-ink-soft">
            <b className="font-serif text-3xl text-ink">{rec.hero_points}</b> pts · colour +{rec.hero_color_bonus}
          </span>
        )}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {hero.known_hand.length === 0 && <span className="text-sm text-ink-soft">No cards yet.</span>}
        {[...hero.known_hand].sort(byName).map((c) => <CardChip key={c.id} card={c} />)}
      </div>
      {hero.played_duos.length > 0 && (
        <>
          <div className="crease-x my-3" />
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-ink-soft">Played duos</h3>
          <div className="flex flex-wrap gap-1.5">
            {hero.played_duos.map((c) => <CardChip key={c.id} card={c} />)}
          </div>
        </>
      )}
    </section>
  );
}
