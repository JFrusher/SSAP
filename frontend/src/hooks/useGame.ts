import { useCallback, useEffect, useState } from "react";
import type { Action, Card, GameState, KeepAdvice, Recommendation, StateResponse } from "../types";

const STORAGE_KEY = "salt-engine-v1";

interface Saved { stack: StateResponse[] }

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`/api/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
  return data as T;
}

const load = (): StateResponse[] => {
  const raw = localStorage.getItem(STORAGE_KEY);
  return raw ? (JSON.parse(raw) as Saved).stack : [];
};

/** Game state lives on the phone; every action round-trips through the stateless engine. */
export function useGame() {
  const [stack, setStack] = useState<StateResponse[]>(load);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ stack: stack.slice(-60) } satisfies Saved));
  }, [stack]);

  const current = stack.at(-1) ?? null;

  const run = useCallback(async (fn: () => Promise<StateResponse>) => {
    setBusy(true);
    setError(null);
    try {
      const next = await fn();
      setStack((s) => [...s, next]);
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }, []);

  const newGame = (names: string[], heroIndex: number) =>
    run(async () => {
      setStack([]);
      return post<StateResponse>("new_game", { names, hero_index: heroIndex });
    });

  const dispatch = (action: Action) => {
    if (!current) throw new Error("no game in progress");
    return run(() => post<StateResponse>("apply", { state: current.state, action }));
  };

  const keepAdvice = (first: Card, second: Card) => {
    if (!current) throw new Error("no game in progress");
    return post<KeepAdvice>("keep", { state: current.state, first, second });
  };

  const undo = () => setStack((s) => (s.length > 1 ? s.slice(0, -1) : s));
  const reset = () => setStack([]);

  return {
    state: (current?.state ?? null) as GameState | null,
    rec: (current?.recommendation ?? null) as Recommendation | null,
    canUndo: stack.length > 1,
    error,
    clearError: () => setError(null),
    busy,
    newGame,
    dispatch,
    keepAdvice,
    undo,
    reset,
  };
}

export type Game = ReturnType<typeof useGame>;
