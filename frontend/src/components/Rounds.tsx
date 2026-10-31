import { useState } from "react";
import { Trophy } from "lucide-react";
import { unseenCounts } from "../cards";
import type { Game } from "../hooks/useGame";
import type { Card, GameState } from "../types";
import { CardChip } from "./CardChip";
import { CardPicker } from "./CardPicker";
import { BigButton } from "./Sheet";

export function Setup({ game }: { game: Game }) {
  const [names, setNames] = useState(["Me", "", ""]);
  const [count, setCount] = useState(2);
  const [hero, setHero] = useState(0);
  const used = names.slice(0, count);
  const valid = used.every((n) => n.trim());

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-black">🐚 SaltEngine</h1>
      <p className="text-white/70">Sea Salt &amp; Paper assistant. Record every move at the table; get live odds and advice.</p>
      <div>
        <div className="mb-2 text-sm text-white/60">Players</div>
        <div className="grid grid-cols-3 gap-2">
          {[2, 3, 4].map((n) => (
            <BigButton key={n} tone={count === n ? "primary" : "default"} onClick={() => {
              setCount(n);
              setNames((xs) => Array.from({ length: Math.max(n, xs.length) }, (_, i) => xs[i] ?? ""));
              if (hero >= n) setHero(0);
            }}>{n}</BigButton>
          ))}
        </div>
      </div>
      <div className="space-y-2">
        <div className="text-sm text-white/60">Names in seating order (first player first). Tap ★ for you.</div>
        {used.map((n, i) => (
          <div key={i} className="flex gap-2">
            <button type="button" onClick={() => setHero(i)} aria-label="This is me"
              className={`w-14 rounded-2xl text-2xl ${hero === i ? "bg-amber-400 text-slate-950" : "bg-white/10"}`}>★</button>
            <input
              value={n}
              onChange={(e) => setNames(names.map((x, j) => (j === i ? e.target.value : x)))}
              placeholder={`Player ${i + 1}`}
              className="min-h-14 flex-1 rounded-2xl bg-white/10 px-4 text-lg outline-none focus:ring-2 focus:ring-sky-400"
            />
          </div>
        ))}
      </div>
      <BigButton tone="good" disabled={!valid || game.busy} onClick={() => game.newGame(used.map((n) => n.trim()), hero)}>
        Start game
      </BigButton>
    </div>
  );
}

export function RoundStart({ game, state }: { game: Game; state: GameState }) {
  const [cards, setCards] = useState<Card[]>([]);
  const [picking, setPicking] = useState(false);
  const last = state.history.at(-1);

  return (
    <div className="space-y-4">
      {last && <RoundSummary state={state} />}
      <h2 className="text-xl font-bold">Round {state.round_number + 1}: set up</h2>
      <p className="text-sm text-white/70">Shuffle, flip the top two cards onto piles A and B, then choose who goes first.</p>
      <div className="flex gap-3">
        {(["A", "B"] as const).map((label, i) => (
          <div key={label} className="flex flex-1 flex-col items-center gap-1">
            {cards[i] ? <CardChip card={cards[i]} size="lg" onClick={() => setCards(cards.slice(0, i))} /> : (
              <button type="button" onClick={() => setPicking(true)} disabled={cards.length !== i}
                className="flex h-24 w-16 items-center justify-center rounded-xl border-2 border-dashed border-white/30 text-2xl disabled:opacity-30">+</button>
            )}
            <span className="text-xs text-white/60">Pile {label}</span>
          </div>
        ))}
      </div>
      {cards.length === 2 && (
        <div className="space-y-2">
          <div className="text-sm text-white/60">Who goes first?</div>
          {state.players.map((p) => (
            <BigButton key={p.player_id} tone="primary" disabled={game.busy}
              onClick={() => game.dispatch({ kind: "start_round", pile_a: cards[0], pile_b: cards[1], first_player_id: p.player_id })}>
              {p.name}
            </BigButton>
          ))}
        </div>
      )}
      {picking && (
        <CardPicker title={`Top card of pile ${cards.length === 0 ? "A" : "B"}`} remaining={unseenCounts(null, cards)}
          onPick={(c) => { setCards([...cards, c]); setPicking(false); }} onClose={() => setPicking(false)} />
      )}
    </div>
  );
}

export function RoundEnd({ game, state }: { game: Game; state: GameState }) {
  const hidden = state.players.filter((p) => p.player_id !== state.hero_id && p.hand_size - p.known_hand.length > 0);
  const [revealed, setRevealed] = useState<Record<string, Card[]>>({});
  const [picking, setPicking] = useState<string | null>(null);
  const all = Object.values(revealed).flat();
  const complete = hidden.every((p) => (revealed[p.player_id]?.length ?? 0) === p.hand_size - p.known_hand.length);
  const reason = { stop: "STOP called", last_chance: "LAST CHANCE resolved", deck_empty: "The deck ran out" }[state.round_end_reason!];

  if (state.round_end_reason === "deck_empty") {
    return (
      <div className="space-y-4">
        <h2 className="text-xl font-bold">{reason}</h2>
        <p className="text-white/70">Nobody scores this round.</p>
        <BigButton tone="good" onClick={() => game.dispatch({ kind: "resolve_round", revealed: {} })}>Continue</BigButton>
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">{reason}: reveal hands</h2>
      <p className="text-sm text-white/70">Enter each opponent's cards you haven't seen yet.</p>
      {hidden.map((p) => {
        const need = p.hand_size - p.known_hand.length;
        const got = revealed[p.player_id] ?? [];
        return (
          <div key={p.player_id} className="rounded-2xl bg-white/5 p-3">
            <div className="mb-2 font-bold">{p.name} <span className="text-sm font-normal text-white/60">{got.length}/{need}</span></div>
            <div className="flex flex-wrap gap-1.5">
              {p.known_hand.map((c) => <CardChip key={c.id} card={c} />)}
              {got.map((c) => (
                <CardChip key={c.id} card={c} selected
                  onClick={() => setRevealed({ ...revealed, [p.player_id]: got.filter((x) => x.id !== c.id) })} />
              ))}
              {got.length < need && (
                <button type="button" onClick={() => setPicking(p.player_id)}
                  className="flex h-14 w-11 items-center justify-center rounded-xl border-2 border-dashed border-white/30 text-xl">+</button>
              )}
            </div>
          </div>
        );
      })}
      <BigButton tone="good" disabled={!complete || game.busy} onClick={() => game.dispatch({ kind: "resolve_round", revealed })}>
        Score the round
      </BigButton>
      {picking && (
        <CardPicker title="Revealed card" remaining={unseenCounts(state, all)}
          onPick={(c) => { setRevealed({ ...revealed, [picking]: [...(revealed[picking] ?? []), c] }); setPicking(null); }}
          onClose={() => setPicking(null)} />
      )}
    </div>
  );
}

export function RoundSummary({ state }: { state: GameState }) {
  const r = state.history.at(-1)!;
  const name = (id: string) => state.players.find((p) => p.player_id === id)!.name;
  return (
    <div className="rounded-2xl bg-white/5 p-3">
      <div className="mb-2 font-bold">
        Round {r.round_number}: {r.reason === "deck_empty" ? "deck ran out" : r.reason === "stop" ? `${name(r.caller_id!)} said STOP` :
          `${name(r.caller_id!)} said LAST CHANCE and ${r.caller_won_bet ? "won" : "lost"} the bet`}
      </div>
      <table className="w-full text-sm">
        <thead className="text-white/50"><tr><th className="text-left">Player</th><th>Cards</th><th>Colour</th><th>Got</th><th>Total</th></tr></thead>
        <tbody>
          {state.players.map((p) => (
            <tr key={p.player_id} className="text-center">
              <td className="text-left">{p.name}</td>
              <td>{r.card_points[p.player_id] ?? "-"}</td>
              <td>{r.color_bonus[p.player_id] ?? "-"}</td>
              <td className="font-bold text-amber-300">+{r.awarded[p.player_id]}</td>
              <td>{p.current_score}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function GameOver({ game, state }: { game: Game; state: GameState }) {
  const winner = state.players.find((p) => p.player_id === state.winner_id)!;
  return (
    <div className="space-y-4 text-center">
      <Trophy size={64} className="mx-auto text-amber-300" />
      <h2 className="text-3xl font-black">{winner.name} wins!</h2>
      <RoundSummary state={state} />
      <BigButton tone="good" onClick={game.reset}>New game</BigButton>
    </div>
  );
}
