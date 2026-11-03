import type { Card, CardName, Color, GameState, Pile } from "./types";

// Display copy of backend DECK_COMPOSITION; the backend stays the authority and rejects overcounts.
export const COMPOSITION: Record<CardName, number> = {
  crab: 9, boat: 8, fish: 7, shark: 5, swimmer: 5,
  shell: 6, octopus: 5, penguin: 3, sailor: 2,
  lighthouse: 1, shoal: 1, colony: 1, captain: 1,
  mermaid: 4,
};

export const CARD_NAMES = Object.keys(COMPOSITION) as CardName[];

export const LABEL: Record<CardName, string> = {
  crab: "Crab", boat: "Boat", fish: "Fish", shark: "Shark", swimmer: "Swimmer",
  shell: "Shell", octopus: "Octopus", penguin: "Penguin", sailor: "Sailor",
  lighthouse: "Lighthouse", shoal: "Shoal of fish", colony: "Penguin colony", captain: "Captain",
  mermaid: "Mermaid",
};

// Colour totals from the ColorADD card in the box (display copy of backend COLOR_COMPOSITION).
export const COLOR_COMPOSITION: Record<Color, number> = {
  light_blue: 9, dark_blue: 9, yellow: 8, black: 8, green: 6, white: 4,
  grey: 4, purple: 4, light_orange: 3, pink: 2, orange: 1,
};

export const COLORS: Color[] = [
  "light_blue", "dark_blue", "yellow", "black", "green", "grey", "purple", "light_orange", "pink", "orange",
];

// Matched to the ColorADD card's swatches.
export const SWATCH: Record<Color, string> = {
  light_blue: "#3BA9BE", dark_blue: "#27338F", yellow: "#E5AE2F", black: "#16161A", green: "#7DC25A",
  grey: "#6B6A6E", purple: "#9A6DC5", light_orange: "#EE9D67", pink: "#E26A9A", orange: "#E5592B", white: "#FFFFFF",
};

// The internal ids are short; the labels follow the card's wording.
const COLOR_LABEL: Record<Color, string> = {
  light_blue: "light blue", dark_blue: "dark blue", yellow: "yellow", black: "black", green: "light green",
  grey: "light grey", purple: "purple", light_orange: "light orange", pink: "light pink", orange: "orange", white: "white",
};
export const colorLabel = (c: Color) => COLOR_LABEL[c];

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

export interface Remaining { names: Record<CardName, number>; colors: Record<Color, number> }

/** Card types and colours not yet seen by the hero this round (deck + opponents' unseen cards). */
export const unseenCounts = (s: GameState | null, extra: Card[] = []): Remaining => {
  const names = { ...COMPOSITION };
  const colors = { ...COLOR_COMPOSITION };
  const seen = !s || s.phase === "round_start" ? extra : [
    ...s.players.flatMap((p) => [...p.known_hand, ...p.played_duos]),
    ...pileCards(s, "a"),
    ...pileCards(s, "b"),
    ...extra,
  ];
  seen.forEach((c) => { names[c.name]--; colors[c.color]--; });
  return { names, colors };
};
