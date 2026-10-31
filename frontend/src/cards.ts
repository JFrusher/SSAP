import type { Card, CardName, Color, GameState, Pile } from "./types";

// Display copy of backend DECK_COMPOSITION; the backend stays the authority and rejects overcounts.
export const COMPOSITION: Record<CardName, number> = {
  crab: 9, boat: 8, fish: 7, shark: 5, swimmer: 5,
  shell: 6, octopus: 5, penguin: 3, sailor: 2,
  lighthouse: 1, shoal: 1, colony: 1, captain: 1,
  mermaid: 4,
};

export const CARD_NAMES = Object.keys(COMPOSITION) as CardName[];

export const EMOJI: Record<CardName, string> = {
  crab: "🦀", boat: "⛵", fish: "🐟", shark: "🦈", swimmer: "🏊",
  shell: "🐚", octopus: "🐙", penguin: "🐧", sailor: "🧑‍✈️",
  lighthouse: "🗼", shoal: "🐠", colony: "🏘️", captain: "⚓",
  mermaid: "🧜",
};

export const LABEL: Record<CardName, string> = {
  crab: "Crab", boat: "Boat", fish: "Fish", shark: "Shark", swimmer: "Swimmer",
  shell: "Shell", octopus: "Octopus", penguin: "Penguin", sailor: "Sailor",
  lighthouse: "Lighthouse", shoal: "Shoal of fish", colony: "Penguin colony", captain: "Captain",
  mermaid: "Mermaid",
};

export const COLORS: Color[] = [
  "dark_blue", "light_blue", "black", "yellow", "green", "purple", "grey", "light_orange", "pink", "orange",
];

export const SWATCH: Record<Color, string> = {
  dark_blue: "#1e3a8a", light_blue: "#7dd3fc", black: "#111827", yellow: "#facc15", green: "#4ade80",
  purple: "#a855f7", grey: "#9ca3af", light_orange: "#fdba74", pink: "#f472b6", orange: "#f97316", white: "#ffffff",
};

export const colorLabel = (c: Color) => c.replace("_", " ");

export const newCard = (name: CardName, color: Color): Card => ({
  id: Math.random().toString(36).slice(2, 10),
  name,
  color,
});

export const pileCards = (s: GameState, pile: Pile): Card[] => {
  let stack: Card[] = [];
  for (const e of s.discard_ledger.entries) {
    if (e.pile !== pile) continue;
    stack = e.direction === "in" ? [...stack, e.card] : stack.filter((c) => c.id !== e.card.id);
  }
  return stack;
};

/** Cards of each name not yet seen by the hero this round (deck + opponents' unseen cards). */
export const unseenCounts = (s: GameState | null, extra: Card[] = []): Record<CardName, number> => {
  const left = { ...COMPOSITION };
  if (!s || s.phase === "round_start") {
    extra.forEach((c) => left[c.name]--);
    return left;
  }
  const seen = [
    ...s.players.flatMap((p) => [...p.known_hand, ...p.played_duos]),
    ...pileCards(s, "a"),
    ...pileCards(s, "b"),
    ...extra,
  ];
  seen.forEach((c) => left[c.name]--);
  return left;
};
