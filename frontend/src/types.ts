// Mirrors backend/engine/models.py, backend/engine/rules.py and backend/solver/ev_calculator.py.

export type CardName =
  | "crab" | "boat" | "fish" | "shark" | "swimmer"
  | "shell" | "octopus" | "penguin" | "sailor"
  | "lighthouse" | "shoal" | "colony" | "captain"
  | "mermaid";

export type Color =
  | "dark_blue" | "light_blue" | "black" | "yellow" | "green"
  | "purple" | "grey" | "light_orange" | "pink" | "orange" | "white";

export type Pile = "a" | "b";

export interface Card { id: string; name: CardName; color: Color }

export interface LedgerEntry { direction: "in" | "out"; pile: Pile; card: Card; player_id: string | null }

export interface PlayerState {
  player_id: string;
  name: string;
  is_human: boolean;
  hand_size: number;
  known_hand: Card[];
  played_duos: Card[];
  current_score: number;
  passed_on: Partial<Record<CardName, number>>;
}

export interface RoundResult {
  round_number: number;
  reason: "stop" | "last_chance" | "deck_empty";
  caller_id: string | null;
  caller_won_bet: boolean | null;
  card_points: Record<string, number>;
  color_bonus: Record<string, number>;
  awarded: Record<string, number>;
}

export interface GameState {
  players: PlayerState[];
  hero_id: string;
  active_player_id: string;
  deck_count: number;
  discard_ledger: { entries: LedgerEntry[] };
  phase: "round_start" | "draw" | "play_duo" | "round_end" | "game_over";
  round_number: number;
  target_score: number;
  extra_turn_pending: boolean;
  last_chance_caller: string | null;
  last_chance_queue: string[];
  round_end_reason: "stop" | "last_chance" | "deck_empty" | null;
  history: RoundResult[];
  winner_id: string | null;
}

export type Action =
  | { kind: "start_round"; pile_a: Card; pile_b: Card; first_player_id: string }
  | { kind: "draw_deck"; kept: Card | null; discarded: Card | null; pile: Pile | null }
  | { kind: "take_discard"; pile: Pile }
  | {
      kind: "play_duo";
      cards: [Card, Card];
      crab_pile?: Pile | null;
      crab_card_id?: string | null;
      fish_card?: Card | null;
      steal_from?: string | null;
      stolen_card?: Card | null;
    }
  | { kind: "end_turn"; call: "stop" | "last_chance" | null }
  | { kind: "resolve_round"; revealed: Record<string, Card[]> };

export interface DrawOption { source: "deck" | Pile; card: Card | null; ev: number }
export interface DuoOption { duo: "crab" | "boat" | "fish" | "shark"; effect: string; effect_ev: number }
export interface EndRoundAdvice {
  hero_points: number;
  stop_margin: number;
  last_chance_margin: number;
  p_last_chance_win: number;
  best: "stop" | "last_chance" | "continue";
}
export interface OpponentView {
  player_id: string;
  hand_size: number;
  unseen: number;
  expected_hand: Partial<Record<CardName, number>>;
  p_holds_mermaid: number;
  est_points: number;
  p_can_end: number;
}
export interface Recommendation {
  hero_points: number;
  hero_color_bonus: number;
  deck: Partial<Record<CardName, number>>;
  draw: DrawOption[] | null;
  best_draw: "deck" | Pile | null;
  duos: DuoOption[] | null;
  end_round: EndRoundAdvice | null;
  opponents: OpponentView[];
}
export interface StateResponse { state: GameState; recommendation: Recommendation | null }
export interface KeepAdvice { keep_index: 0 | 1; values: [number, number] }
