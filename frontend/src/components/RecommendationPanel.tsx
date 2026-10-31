import { Sparkles } from "lucide-react";
import { EMOJI } from "../cards";
import type { GameState, Recommendation } from "../types";

const SOURCE: Record<string, string> = { deck: "Draw 2 from deck", a: "Take pile A", b: "Take pile B" };
const DUO_EMOJI = { crab: "🦀🦀", boat: "⛵⛵", fish: "🐟🐟", shark: "🦈🏊" };
const CALL = { stop: "STOP", last_chance: "LAST CHANCE", continue: "Keep playing" };

export function RecommendationPanel({ state, rec }: { state: GameState; rec: Recommendation | null }) {
  if (!rec) return null;
  const heroTurn = state.active_player_id === state.hero_id;
  return (
    <section className="rounded-2xl bg-gradient-to-br from-indigo-900/80 to-sky-900/60 p-3">
      <h2 className="mb-2 flex items-center gap-2 font-bold">
        <Sparkles size={18} className="text-amber-300" /> Advice
      </h2>

      {!heroTurn && <p className="text-sm text-white/70">Opponent's turn: record what they do below.</p>}

      {rec.draw && (
        <ul className="space-y-1.5">
          {[...rec.draw].sort((a, b) => b.ev - a.ev).map((o) => {
            const best = o.source === rec.best_draw;
            return (
              <li key={o.source} className={`flex items-center justify-between rounded-xl px-3 py-2 ${best ? "bg-amber-400 text-slate-950" : "bg-white/10"}`}>
                <span className="font-semibold">
                  {o.card ? `${EMOJI[o.card.name]} ` : "🂠 "}{SOURCE[o.source]}
                </span>
                <span className="tabular-nums">{o.ev.toFixed(2)} EV</span>
              </li>
            );
          })}
        </ul>
      )}

      {rec.duos && rec.duos.length > 0 && (
        <div className="space-y-1.5">
          {rec.duos.map((d) => (
            <div key={d.duo} className="flex items-center justify-between rounded-xl bg-emerald-500/20 px-3 py-2 text-sm">
              <span>Play {DUO_EMOJI[d.duo]}: {d.effect}</span>
              <span className="tabular-nums">+{d.effect_ev.toFixed(2)}</span>
            </div>
          ))}
          <p className="text-xs text-white/60">Playing banks the point now and protects the pair from steals.</p>
        </div>
      )}

      {rec.end_round && (
        <div className="mt-3 rounded-xl bg-black/30 p-3">
          <div className="text-xs uppercase tracking-wide text-white/60">You can end the round</div>
          <div className="text-2xl font-black text-amber-300">{CALL[rec.end_round.best]}</div>
          <div className="mt-2 text-sm">Last Chance win: <b>{Math.round(rec.end_round.p_last_chance_win * 100)}%</b></div>
          <div className="mt-1 h-2 overflow-hidden rounded bg-white/10">
            <div className="h-full bg-gradient-to-r from-rose-500 via-amber-400 to-emerald-400" style={{ width: `${rec.end_round.p_last_chance_win * 100}%` }} />
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2 text-center text-sm">
            <div className="rounded-lg bg-white/10 p-2">Stop<br /><b>{signed(rec.end_round.stop_margin)}</b></div>
            <div className="rounded-lg bg-white/10 p-2">Last Chance<br /><b>{signed(rec.end_round.last_chance_margin)}</b></div>
          </div>
          <p className="mt-1 text-xs text-white/50">Expected round points vs the best opponent.</p>
        </div>
      )}

      {heroTurn && state.phase === "play_duo" && state.extra_turn_pending && (
        <p className="mt-2 rounded-xl bg-sky-500/20 px-3 py-2 text-sm">⛵⛵ Boats played: tap <b>Extra turn</b> to draw again.</p>
      )}
      {heroTurn && state.phase === "play_duo" && !state.extra_turn_pending && !rec.end_round && (!rec.duos || rec.duos.length === 0) && (
        <p className="text-sm text-white/70">No duo to play. End your turn.</p>
      )}
    </section>
  );
}

const signed = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}`;
