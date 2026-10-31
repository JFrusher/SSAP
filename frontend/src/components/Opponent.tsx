import { LABEL } from "../cards";
import type { CardName, OpponentView, PlayerState } from "../types";
import { CardArt } from "./CardArt";
import { CardChip } from "./CardChip";

interface Props {
  player: PlayerState;
  view: OpponentView | undefined;
  active: boolean;
}

export function Opponent({ player, view, active }: Props) {
  const likely = view
    ? (Object.entries(view.expected_hand) as [CardName, number][]).filter(([, v]) => v >= 0.5).sort((a, b) => b[1] - a[1]).slice(0, 4)
    : [];
  const threat = view?.p_can_end ?? 0;
  return (
    <section
      aria-label={`${player.name}${active ? ", playing now" : ""}`}
      className={`paper min-w-[12rem] flex-1 p-3 ${active ? "border-2 border-navy" : ""}`}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="truncate font-serif text-lg font-bold">{player.name}</span>
        <span className="shrink-0 text-sm"><b className="font-serif text-xl">{player.current_score}</b> pts</span>
      </div>
      <div className="text-xs text-ink-soft">
        {player.hand_size} in hand{view ? ` · ${view.unseen} unseen` : ""}{active ? " · playing" : ""}
      </div>
      {player.known_hand.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">{player.known_hand.map((c) => <CardChip key={c.id} card={c} />)}</div>
      )}
      {player.played_duos.length > 0 && (
        <div className="mt-2 flex items-center gap-1 text-xs text-ink-soft">
          Duos
          {player.played_duos.map((c) => <CardArt key={c.id} name={c.name} color={c.color} className="h-5 w-5" />)}
        </div>
      )}
      {view && (
        <>
          <div className="mt-2 flex items-center justify-between text-xs">
            <span>~{view.est_points} pts</span>
            <span>Could end round: <b className={threat > 0.5 ? "text-vermilion" : "text-sea"}>{Math.round(threat * 100)}%</b></span>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-crease" role="presentation">
            <div className="h-full bg-vermilion" style={{ width: `${threat * 100}%` }} />
          </div>
          {likely.length > 0 && (
            <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-soft">
              Likely
              {likely.map(([n, v]) => (
                <span key={n} className="inline-flex items-center" title={LABEL[n]}>
                  <CardArt name={n} color={null} className="h-5 w-5" /><span className="sr-only">{LABEL[n]}</span>×{v.toFixed(1)}
                </span>
              ))}
            </div>
          )}
          {view.p_holds_mermaid > 0.05 && (
            <div className="mt-1 flex items-center gap-1 text-xs text-ink-soft">
              <CardArt name="mermaid" color="white" className="h-5 w-5" /> mermaid {Math.round(view.p_holds_mermaid * 100)}%
            </div>
          )}
        </>
      )}
    </section>
  );
}
