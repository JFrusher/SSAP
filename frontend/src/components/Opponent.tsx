import { EMOJI } from "../cards";
import type { CardName, OpponentView, PlayerState } from "../types";
import { CardChip } from "./CardChip";

interface Props {
  player: PlayerState;
  view: OpponentView | undefined;
  active: boolean;
}

export function Opponent({ player, view, active }: Props) {
  const likely = view
    ? (Object.entries(view.expected_hand) as [CardName, number][])
        .filter(([, v]) => v >= 0.5)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 4)
    : [];
  const threat = view?.p_can_end ?? 0;
  return (
    <div className={`min-w-[11rem] flex-1 rounded-2xl p-3 ${active ? "bg-amber-400/15 ring-2 ring-amber-400" : "bg-white/5"}`}>
      <div className="flex items-baseline justify-between">
        <span className="truncate font-bold">{player.name}</span>
        <span className="text-sm text-white/60">{player.current_score} pts</span>
      </div>
      <div className="text-xs text-white/60">
        {player.hand_size} in hand · {view ? `${view.unseen} unseen` : ""}
      </div>
      {player.known_hand.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1">
          {player.known_hand.map((c) => <CardChip key={c.id} card={c} />)}
        </div>
      )}
      {player.played_duos.length > 0 && (
        <div className="mt-1 text-sm">Duos: {player.played_duos.map((c) => EMOJI[c.name]).join("")}</div>
      )}
      {view && (
        <>
          <div className="mt-2 text-xs">
            ~{view.est_points} pts · can end: <b className={threat > 0.5 ? "text-rose-400" : "text-emerald-300"}>{Math.round(threat * 100)}%</b>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded bg-white/10">
            <div className="h-full bg-rose-500" style={{ width: `${threat * 100}%` }} />
          </div>
          {likely.length > 0 && (
            <div className="mt-1 text-xs text-white/60">
              Likely: {likely.map(([n, v]) => `${EMOJI[n]}${v.toFixed(1)}`).join(" ")}
            </div>
          )}
          {view.p_holds_mermaid > 0.05 && (
            <div className="text-xs text-white/60">🧜 {Math.round(view.p_holds_mermaid * 100)}%</div>
          )}
        </>
      )}
    </div>
  );
}
