import { useEffect, useState } from "react";
import { ArrowDownToLine, Flag, Hand as HandIcon, Layers, Play, Sailboat, Siren } from "lucide-react";
import { EMOJI, pileCards, unseenCounts } from "../cards";
import type { Game } from "../hooks/useGame";
import type { Action, Card, CardName, GameState, KeepAdvice, Pile, PlayerState } from "../types";
import { CardChip } from "./CardChip";
import { CardPicker } from "./CardPicker";
import { BigButton, Sheet } from "./Sheet";

type Duo = "crab" | "boat" | "fish" | "shark";
const DUO_CARDS: Record<Duo, [CardName, CardName]> = {
  crab: ["crab", "crab"], boat: ["boat", "boat"], fish: ["fish", "fish"], shark: ["shark", "swimmer"],
};
const DUO_LABEL: Record<Duo, string> = { crab: "🦀🦀 Crabs", boat: "⛵⛵ Boats", fish: "🐟🐟 Fish", shark: "🦈🏊 Shark + Swimmer" };

type Flow = { k: "heroDeck" } | { k: "oppDeck" } | { k: "duo"; duo: Duo } | { k: "pickDuo" } | null;

const emptyPiles = (s: GameState) => (["a", "b"] as Pile[]).filter((p) => pileCards(s, p).length === 0);

/** Pairs the hero can play from hand. */
const heroDuos = (hero: PlayerState): Duo[] => {
  const n = (x: CardName) => hero.known_hand.filter((c) => c.name === x).length;
  return (Object.keys(DUO_CARDS) as Duo[]).filter((d) =>
    d === "shark" ? n("shark") >= 1 && n("swimmer") >= 1 : n(d) >= 2,
  );
};

export function Actions({ game, state }: { game: Game; state: GameState }) {
  const [flow, setFlow] = useState<Flow>(null);
  const active = state.players.find((p) => p.player_id === state.active_player_id)!;
  const heroTurn = active.player_id === state.hero_id;
  // Opponents' points are hidden, so only the hero's 7-point minimum can be checked here.
  const canCall = state.last_chance_caller === null && (!heroTurn || (game.rec?.hero_points ?? 0) >= 7);
  const done = async (a: Action) => {
    if (await game.dispatch(a)) setFlow(null);
  };
  const close = () => setFlow(null);

  return (
    <div className="space-y-2">
      {state.phase === "draw" && (
        <div className="grid grid-cols-3 gap-2">
          <BigButton tone="primary" onClick={() => setFlow({ k: heroTurn ? "heroDeck" : "oppDeck" })} disabled={state.deck_count === 0}>
            <Layers size={18} /> Deck
          </BigButton>
          {(["a", "b"] as Pile[]).map((p) => (
            <BigButton key={p} onClick={() => done({ kind: "take_discard", pile: p })} disabled={pileCards(state, p).length === 0}>
              <ArrowDownToLine size={18} /> Pile {p.toUpperCase()}
            </BigButton>
          ))}
        </div>
      )}

      {state.phase === "play_duo" && (
        <>
          <BigButton tone="good" onClick={() => setFlow({ k: "pickDuo" })} disabled={heroTurn && heroDuos(active).length === 0}>
            <Play size={18} /> Play a duo
          </BigButton>
          <div className="grid grid-cols-3 gap-2">
            <BigButton tone="primary" onClick={() => done({ kind: "end_turn", call: null })}>
              {state.extra_turn_pending ? <><Sailboat size={18} /> Extra turn</> : <><HandIcon size={18} /> End turn</>}
            </BigButton>
            <BigButton tone="danger" onClick={() => done({ kind: "end_turn", call: "stop" })} disabled={!canCall}>
              <Flag size={18} /> Stop
            </BigButton>
            <BigButton tone="danger" onClick={() => done({ kind: "end_turn", call: "last_chance" })} disabled={!canCall}>
              <Siren size={18} /> Last chance
            </BigButton>
          </div>
        </>
      )}

      {flow?.k === "heroDeck" && <HeroDeckFlow game={game} state={state} onDone={done} onClose={close} />}
      {flow?.k === "oppDeck" && <OppDeckFlow state={state} onDone={done} onClose={close} />}
      {flow?.k === "pickDuo" && (
        <Sheet title="Which duo?" onClose={close}>
          <div className="space-y-2">
            {(heroTurn ? heroDuos(active) : (Object.keys(DUO_CARDS) as Duo[])).map((d) => (
              <BigButton key={d} onClick={() => setFlow({ k: "duo", duo: d })}>{DUO_LABEL[d]}</BigButton>
            ))}
          </div>
        </Sheet>
      )}
      {flow?.k === "duo" && <DuoFlow state={state} duo={flow.duo} onDone={done} onClose={close} />}
    </div>
  );
}

// ---------------------------------------------------------------- draw from deck

function ChoosePile({ state, title, advice, onPick, onClose }: {
  state: GameState;
  title: string;
  advice?: { pile: Pile; risk: Partial<Record<Pile, number>> };
  onPick: (p: Pile) => void;
  onClose: () => void;
}) {
  const forced = emptyPiles(state);
  useEffect(() => {
    if (forced.length === 1) onPick(forced[0]);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  if (forced.length === 1) return null;
  return (
    <Sheet title={title} onClose={onClose}>
      <div className="grid grid-cols-2 gap-2">
        {(["a", "b"] as Pile[]).map((p) => (
          <div key={p} className="flex flex-col items-center gap-1">
            <BigButton tone={advice?.pile === p ? "primary" : "default"} onClick={() => onPick(p)}>Pile {p.toUpperCase()}</BigButton>
            {advice && advice.risk[p] !== undefined && (
              <span className="text-xs text-white/70">next player gains ~{advice.risk[p]!.toFixed(2)}</span>
            )}
            {advice?.pile === p && <span className="text-xs font-bold text-amber-300">Recommended</span>}
          </div>
        ))}
      </div>
      {advice && <p className="mt-3 text-xs text-white/50">Discarding buries that pile's top card. The recommended pile leaves the next player the least to take.</p>}
    </Sheet>
  );
}

function HeroDeckFlow({ game, state, onDone, onClose }: { game: Game; state: GameState; onDone: (a: Action) => void; onClose: () => void }) {
  const [drawn, setDrawn] = useState<Card[]>([]);
  const [advice, setAdvice] = useState<KeepAdvice | null>(null);
  const [keep, setKeep] = useState<0 | 1 | null>(null);
  const single = state.deck_count === 1;

  useEffect(() => {
    if (single && drawn.length === 1) onDone({ kind: "draw_deck", kept: drawn[0], discarded: null, pile: null });
    if (drawn.length === 2) game.keepAdvice(drawn[0], drawn[1]).then(setAdvice);
  }, [drawn]); // eslint-disable-line react-hooks/exhaustive-deps

  if (drawn.length < (single ? 1 : 2)) {
    return (
      <CardPicker
        key={drawn.length}
        title={drawn.length === 0 ? "First card drawn" : "Second card drawn"}
        remaining={unseenCounts(state, drawn)}
        onPick={(c) => setDrawn([...drawn, c])}
        onClose={onClose}
      />
    );
  }
  if (single) return null;
  if (keep === null) {
    return (
      <Sheet title="Tap the card to keep" onClose={onClose}>
        <div className="flex justify-center gap-6">
          {drawn.map((c, i) => (
            <div key={c.id} className="flex flex-col items-center gap-2">
              <CardChip card={c} size="lg" selected={advice?.keep_index === i} onClick={() => setKeep(i as 0 | 1)} />
              <span className="text-sm tabular-nums">{advice ? `${advice.values[i].toFixed(2)} EV` : "…"}</span>
              {advice?.keep_index === i && <span className="text-xs font-bold text-amber-300">Recommended</span>}
            </div>
          ))}
        </div>
      </Sheet>
    );
  }
  const discarded = drawn[1 - keep];
  return (
    <ChoosePile
      state={state}
      title={`Discard ${EMOJI[discarded.name]} onto…`}
      advice={advice && advice.keep_index === keep ? { pile: advice.discard_pile, risk: advice.pile_risk } : undefined}
      onPick={(p) => onDone({ kind: "draw_deck", kept: drawn[keep], discarded, pile: p })}
      onClose={onClose}
    />
  );
}

function OppDeckFlow({ state, onDone, onClose }: { state: GameState; onDone: (a: Action) => void; onClose: () => void }) {
  const [discarded, setDiscarded] = useState<Card | null>(null);
  useEffect(() => {
    if (state.deck_count === 1) onDone({ kind: "draw_deck", kept: null, discarded: null, pile: null });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  if (state.deck_count === 1) return null;
  if (!discarded) {
    return <CardPicker title="Card they discarded" remaining={unseenCounts(state)} onPick={setDiscarded} onClose={onClose} />;
  }
  return (
    <ChoosePile
      state={state}
      title={`They discarded ${EMOJI[discarded.name]} onto…`}
      onPick={(p) => onDone({ kind: "draw_deck", kept: null, discarded, pile: p })}
      onClose={onClose}
    />
  );
}

// ---------------------------------------------------------------- duos

/** Pick one of the listed known cards, or (for opponents) an unseen card via the picker. */
function ChooseCard({ title, cards, unseen, onPick, onClose }: {
  title: string;
  cards: Card[];
  unseen: { remaining: Record<CardName, number>; only?: CardName[] } | null;
  onPick: (c: Card) => void;
  onClose: () => void;
}) {
  const [picker, setPicker] = useState(false);
  useEffect(() => {
    if (cards.length === 0 && unseen) setPicker(true);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  if (picker && unseen) return <CardPicker title={title} remaining={unseen.remaining} only={unseen.only} onPick={onPick} onClose={onClose} />;
  return (
    <Sheet title={title} onClose={onClose}>
      <div className="flex flex-wrap gap-2">
        {cards.map((c) => <CardChip key={c.id} card={c} size="lg" onClick={() => onPick(c)} />)}
      </div>
      {unseen && (
        <div className="mt-3">
          <BigButton onClick={() => setPicker(true)}>A card I hadn't seen…</BigButton>
        </div>
      )}
    </Sheet>
  );
}

function DuoFlow({ state, duo, onDone, onClose }: { state: GameState; duo: Duo; onDone: (a: Action) => void; onClose: () => void }) {
  const player = state.players.find((p) => p.player_id === state.active_player_id)!;
  const isHero = player.player_id === state.hero_id;
  const hero = state.players.find((p) => p.player_id === state.hero_id)!;
  const [first, second] = DUO_CARDS[duo];
  const matching = (name: CardName, exclude: Card[]) =>
    player.known_hand.filter((c) => c.name === name && !exclude.some((e) => e.id === c.id));

  // The hero's cards are known: take them straight from hand.
  const auto: Card[] = isHero ? [matching(first, [])[0], matching(second, [matching(first, [])[0]])[0]] : [];
  const [cards, setCards] = useState<Card[]>(auto);
  const [victim, setVictim] = useState<PlayerState | null>(null);
  const [crabPile, setCrabPile] = useState<Pile | null>(null);

  const pair = cards as [Card, Card];
  const base = { kind: "play_duo" as const, cards: pair };

  // 1) the two cards (opponents only)
  if (cards.length < 2) {
    const name = cards.length === 0 ? first : second;
    return (
      <ChooseCard
        key={cards.length}
        title={`${player.name}'s ${EMOJI[name]} card`}
        cards={matching(name, cards)}
        unseen={{ remaining: unseenCounts(state, cards), only: [name] }}
        onPick={(c) => setCards([...cards, c])}
        onClose={onClose}
      />
    );
  }

  // 2) the effect
  if (duo === "boat") {
    return <Confirm label={`${DUO_LABEL[duo]}: extra turn`} onConfirm={() => onDone(base)} onClose={onClose} />;
  }

  if (duo === "fish") {
    if (!isHero || state.deck_count === 0) {
      return <Confirm label={`${DUO_LABEL[duo]}: draw top card`} onConfirm={() => onDone(base)} onClose={onClose} />;
    }
    return (
      <CardPicker title="Card you drew" remaining={unseenCounts(state)} onPick={(c) => onDone({ ...base, fish_card: c })} onClose={onClose} />
    );
  }

  if (duo === "crab") {
    const piles = (["a", "b"] as Pile[]).filter((p) => pileCards(state, p).length > 0);
    if (piles.length === 0) return <Confirm label="Both piles are empty: no effect" onConfirm={() => onDone(base)} onClose={onClose} />;
    if (!crabPile) {
      return (
        <Sheet title={isHero ? "Which pile do you search?" : "Which pile did they search?"} onClose={onClose}>
          <div className="grid grid-cols-2 gap-2">
            {piles.map((p) => <BigButton key={p} onClick={() => setCrabPile(p)}>Pile {p.toUpperCase()}</BigButton>)}
          </div>
        </Sheet>
      );
    }
    return (
      <ChooseCard
        title="Card taken from the pile"
        cards={[...pileCards(state, crabPile)].reverse()}
        unseen={null}
        onPick={(c) => onDone({ ...base, crab_pile: crabPile, crab_card_id: c.id })}
        onClose={onClose}
      />
    );
  }

  // shark + swimmer
  const targets = state.players.filter((p) => p.player_id !== player.player_id && p.hand_size > 0);
  if (targets.length === 0) return <Confirm label="Nobody has cards: no effect" onConfirm={() => onDone(base)} onClose={onClose} />;
  if (!victim) {
    return (
      <Sheet title="Stolen from…" onClose={onClose}>
        <div className="space-y-2">
          {targets.map((p) => (
            <BigButton key={p.player_id} onClick={() => setVictim(p)}>
              {p.player_id === state.hero_id ? "Me" : p.name} ({p.hand_size} cards)
            </BigButton>
          ))}
        </div>
      </Sheet>
    );
  }
  const heroInvolved = isHero || victim.player_id === hero.player_id;
  if (!heroInvolved) {
    return (
      <Confirm label={`${player.name} steals a hidden card from ${victim.name}`} onConfirm={() => onDone({ ...base, steal_from: victim.player_id })} onClose={onClose} />
    );
  }
  const victimIsHero = victim.player_id === hero.player_id;
  return (
    <ChooseCard
      title={victimIsHero ? "Card stolen from you" : `Card you stole from ${victim.name}`}
      cards={victim.known_hand}
      unseen={victimIsHero || victim.known_hand.length === victim.hand_size ? null : { remaining: unseenCounts(state) }}
      onPick={(c) => onDone({ ...base, steal_from: victim.player_id, stolen_card: c })}
      onClose={onClose}
    />
  );
}

function Confirm({ label, onConfirm, onClose }: { label: string; onConfirm: () => void; onClose: () => void }) {
  return (
    <Sheet title="Confirm" onClose={onClose}>
      <p className="mb-3">{label}</p>
      <BigButton tone="good" onClick={onConfirm}>Confirm</BigButton>
    </Sheet>
  );
}
