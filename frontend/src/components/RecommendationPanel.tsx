import { Layers } from "lucide-react";
import type { GameState, Recommendation } from "../types";
import { CardArt } from "./CardArt";

const SOURCE: Record<string, string> = { deck: "Draw 2 from the deck", a: "Take pile A", b: "Take pile B" };
const DUO_LABEL = { crab: "crabs", boat: "boats", fish: "fish", shark: "shark + swimmer" };
const CALL = { stop: "Stop", last_chance: "Last Chance", continue: "Keep playing" };
const ACTION: Record<string, string> = {
  "draw:deck": "Draw 2 from the deck", "draw:a": "Take pile A", "draw:b": "Take pile B",
  "duo:crab": "Play two crabs", "duo:boat": "Play two boats", "duo:fish": "Play two fish", "duo:shark": "Play shark + swimmer",
  "end:none": "End turn, keep playing", "end:stop": "Stop", "end:last_chance": "Last Chance",
};

export function RecommendationPanel({ state, rec }: { state: GameState; rec: Recommendation | null }) {
  if (!rec) return null;
  const heroTurn = state.active_player_id === state.hero_id;
  return (
    <section className="paper p-3" aria-label="Advice" aria-live="polite">
      <h2 className="mb-2 font-serif text-lg font-bold">Advice</h2>

      {!heroTurn && <p className="text-sm text-ink-soft">Opponent's turn. Record what they do below.</p>}

      {rec.search && Object.keys(rec.search).length > 1 && (
        <div className="mb-3">
          <ol className="space-y-1">
            {Object.entries(rec.search).sort((a, b) => b[1] - a[1]).map(([a, m]) => (
              <li key={a} className={`flex items-center justify-between gap-2 rounded-[3px] px-3 py-1.5 text-sm ${a === rec.search_best ? "border-2 border-vermilion bg-vermilion/5 font-semibold" : "border border-crease"}`}>
                <span>{ACTION[a] ?? a}</span>
                <span className="flex items-center gap-2 tabular-nums">{a === rec.search_best && <span className="stamp">play this</span>}{signed(m)}</span>
              </li>
            ))}
          </ol>
          <p className="mt-1 text-xs text-ink-soft">Simulated to the end of the round from many possible deals. Number: expected round points vs the best opponent.</p>
        </div>
      )}

      {rec.draw && !rec.search && (
        <ol className="space-y-1.5">
          {[...rec.draw].sort((a, b) => Number(b.source === rec.best_draw) - Number(a.source === rec.best_draw) || b.ev - a.ev).map((o) => {
            const best = o.source === rec.best_draw;
            return (
              <li key={o.source} className={`flex items-center justify-between gap-2 rounded-[3px] px-3 py-2 ${best ? "border-2 border-vermilion bg-vermilion/5" : "border border-crease"}`}>
                <span className="flex items-center gap-2 font-semibold">
                  {o.card ? <CardArt name={o.card.name} color={o.card.color} className="h-7 w-7" /> : <Layers size={22} aria-hidden="true" />}
                  {SOURCE[o.source]}
                </span>
                <span className="flex items-center gap-2 tabular-nums">
                  {best && <span className="stamp">best</span>}
                  {o.ev.toFixed(2)}
                </span>
              </li>
            );
          })}
        </ol>
      )}
      {rec.draw && !rec.search && <p className="mt-1.5 text-xs text-ink-soft">Expected points from this draw and your next one.</p>}

      {rec.duos && rec.duos.length > 0 && (
        <ul className="space-y-1.5">
          {rec.duos.map((d) => (
            <li key={d.duo} className="flex items-center justify-between gap-2 rounded-[3px] border-2 border-sea bg-sea/5 px-3 py-2 text-sm">
              <span className="flex items-center gap-2">
                <CardArt name={d.duo === "shark" ? "shark" : d.duo} color={null} className="h-7 w-7" />
                Play the {DUO_LABEL[d.duo]}: {d.effect}
              </span>
              <span className="tabular-nums">+{d.effect_ev.toFixed(2)}</span>
            </li>
          ))}
          <li className="text-xs text-ink-soft">Playing banks the point now and protects the pair from steals.</li>
        </ul>
      )}

      {rec.end_round && (
        <div className="mt-3 rounded-[3px] border-2 border-ink p-3">
          <div className="text-xs font-semibold uppercase tracking-wider text-ink-soft">You can end the round</div>
          <div className="mt-1 flex items-center gap-3">
            <span className="font-serif text-3xl font-bold">{CALL[rec.end_round.best]}</span>
            <span className="stamp">advised</span>
          </div>
          <div className="mt-2 text-sm">Chance Last Chance pays off: <b>{Math.round(rec.end_round.p_last_chance_win * 100)}%</b></div>
          <div className="mt-1 h-2 overflow-hidden rounded-full bg-crease" role="presentation">
            <div className="h-full bg-navy" style={{ width: `${rec.end_round.p_last_chance_win * 100}%` }} />
          </div>
          {!rec.search && (
            <>
          <div className="mt-3 grid grid-cols-2 gap-2 text-center text-sm">
            <div className="rounded-[3px] border border-crease p-2">Stop<br /><b className="font-serif text-lg">{signed(rec.end_round.stop_margin)}</b></div>
            <div className="rounded-[3px] border border-crease p-2">Last Chance<br /><b className="font-serif text-lg">{signed(rec.end_round.last_chance_margin)}</b></div>
          </div>
          <p className="mt-1.5 text-xs text-ink-soft">Expected round points compared with the best opponent.</p>
            </>
          )}
        </div>
      )}

      {heroTurn && state.phase === "play_duo" && state.extra_turn_pending && (
        <p className="mt-2 flex items-center gap-2 rounded-[3px] border-2 border-navy px-3 py-2 text-sm">
          <CardArt name="boat" color={null} className="h-7 w-7" /> Boats played: tap <b>Extra turn</b> to draw again.
        </p>
      )}
      {heroTurn && state.phase === "play_duo" && !state.extra_turn_pending && !rec.end_round && (!rec.duos || rec.duos.length === 0) && (
        <p className="text-sm text-ink-soft">No duo to play. End your turn.</p>
      )}
    </section>
  );
}

const signed = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}`;
