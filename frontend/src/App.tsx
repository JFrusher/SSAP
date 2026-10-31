import { RotateCcw, Undo2 } from "lucide-react";
import { Actions } from "./components/Actions";
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
    <div className="mx-auto min-h-screen max-w-lg px-3 pb-56 pt-[calc(0.75rem+env(safe-area-inset-top))] text-white">
      {state && (
        <header className="mb-3 flex items-center justify-between">
          <div>
            <div className="font-black">🐚 SaltEngine</div>
            <div className="text-xs text-white/60">Round {state.round_number} · first to {state.target_score}</div>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={game.undo} disabled={!game.canUndo} aria-label="Undo"
              className="flex items-center gap-1 rounded-full bg-white/10 px-4 py-2 text-sm active:bg-white/20 disabled:opacity-30">
              <Undo2 size={16} /> Undo
            </button>
            <button type="button" aria-label="New game"
              onClick={() => confirm("Abandon this game and start a new one?") && game.reset()}
              className="rounded-full bg-white/10 p-2 active:bg-white/20">
              <RotateCcw size={18} />
            </button>
          </div>
        </header>
      )}

      {game.error && (
        <button type="button" onClick={game.clearError}
          className="fixed left-3 right-3 top-[calc(0.75rem+env(safe-area-inset-top))] z-50 rounded-2xl bg-rose-600 p-3 text-left text-sm shadow-xl">
          ⚠️ {game.error} <span className="opacity-70">(tap to dismiss)</span>
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

          <div className="fixed bottom-0 left-0 right-0 z-30 border-t border-white/10 bg-[#0b1d33]/95 px-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] pt-2 backdrop-blur">
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
        <b className={mine ? "text-amber-300" : "text-sky-300"}>{mine ? "Your turn" : `${active.name}'s turn`}</b>: {step}
        {state.last_chance_caller && <span className="ml-1 rounded bg-rose-600 px-1.5 text-xs">LAST CHANCE</span>}
        {state.extra_turn_pending && <span className="ml-1 rounded bg-sky-600 px-1.5 text-xs">+1 turn</span>}
      </div>
    );
  }
}
