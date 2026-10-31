import { RotateCcw, Undo2 } from "lucide-react";
import { Actions } from "./components/Actions";
import { CardArt } from "./components/CardArt";
import { Hand } from "./components/Hand";
import { Opponent } from "./components/Opponent";
import { RecommendationPanel } from "./components/RecommendationPanel";
import { GameOver, RoundEnd, RoundStart, Setup } from "./components/Rounds";
import { Table } from "./components/Table";
import { useGame } from "./hooks/useGame";

export default function App() {
  const game = useGame();
  const { state, rec } = game;

  return (
    <div className="mx-auto min-h-screen max-w-lg px-3 pb-60 pt-[calc(0.75rem+env(safe-area-inset-top))]">
      {state && (
        <header className="mb-3 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-1.5 font-serif text-xl font-bold"><CardArt name="boat" color="dark_blue" className="h-7 w-7" />SaltEngine</div>
            <div className="text-xs text-ink-soft">Round {state.round_number} · first to {state.target_score}</div>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={game.undo} disabled={!game.canUndo} aria-label="Undo"
              className="flex min-h-11 items-center gap-1 rounded-[3px] border-2 border-ink bg-sheet px-3 text-sm font-semibold active:translate-y-px disabled:opacity-30">
              <Undo2 size={16} /> Undo
            </button>
            <button type="button" aria-label="New game"
              onClick={() => confirm("Abandon this game and start a new one?") && game.reset()}
              className="grid h-11 w-11 place-items-center rounded-[3px] border-2 border-ink bg-sheet active:translate-y-px">
              <RotateCcw size={18} />
            </button>
          </div>
        </header>
      )}

      {game.error && (
        <button type="button" onClick={game.clearError}
          role="alert" className="fixed left-3 right-3 top-[calc(0.75rem+env(safe-area-inset-top))] z-50 rounded-[3px] border-2 border-ink bg-vermilion p-3 text-left text-sm text-white shadow-[3px_3px_0_#1F1D1A]">
          {game.error} <span className="opacity-80">(tap to dismiss)</span>
        </button>
      )}

      {!state && <Setup game={game} />}
      {state?.phase === "round_start" && <RoundStart game={game} state={state} />}
      {state?.phase === "round_end" && <RoundEnd game={game} state={state} />}
      {state?.phase === "game_over" && <GameOver game={game} state={state} />}

      {state && (state.phase === "draw" || state.phase === "play_duo") && (
        <main className="space-y-3">
          <div className="flex gap-2 overflow-x-auto pb-1">
            {state.players.filter((p) => p.player_id !== state.hero_id).map((p) => (
              <Opponent key={p.player_id} player={p} active={p.player_id === state.active_player_id}
                view={rec?.opponents.find((o) => o.player_id === p.player_id)} />
            ))}
          </div>
          <Table state={state} highlight={rec?.best_draw ?? null} />
          <RecommendationPanel state={state} rec={rec} />
          <Hand hero={state.players.find((p) => p.player_id === state.hero_id)!} rec={rec} />

          <div className="fixed bottom-0 left-0 right-0 z-30 border-t border-crease bg-paper/95 px-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] pt-2 backdrop-blur">
            <div className="mx-auto max-w-lg">
              <TurnBanner />
              <Actions game={game} state={state} />
            </div>
          </div>
        </main>
      )}
    </div>
  );

  function TurnBanner() {
    if (!state) return null;
    const active = state.players.find((p) => p.player_id === state.active_player_id)!;
    const mine = active.player_id === state.hero_id;
    const step = state.phase === "draw" ? "take a card" : "play duos, then end the turn";
    return (
      <div className="mb-2 text-center text-sm">
        <b className={`font-serif text-base ${mine ? "text-vermilion" : "text-navy"}`}>{mine ? "Your turn" : `${active.name}'s turn`}</b>: {step}
        {state.last_chance_caller && <span className="stamp ml-2">last chance</span>}
        {state.extra_turn_pending && <span className="stamp ml-2 border-navy text-navy">extra turn</span>}
      </div>
    );
  }
}
