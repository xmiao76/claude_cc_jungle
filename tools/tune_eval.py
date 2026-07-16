"""Texel-style evaluation tuning for the Jungle AI.

Pipeline:

1. ``harvest`` — fast self-play games; every post-opening position is
   serialized (pieces, side to move, noisy-move availability, ply) together
   with the eventual game result from Blue's perspective. Positions — not
   features — are stored, so the feature extractor can evolve after harvest.
2. ``fit``  — logistic fit of the eval weights over the harvested positions
   (added with the tuned-weights slice).
3. ``emit`` — print the fitted weight tables as drop-in config code.

Usage (repo root, headless):

    python -m tools.tune_eval harvest --games 500 --budget 120 --out positions.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import time

from ai.minimax import AIPlayer
from ai.search_config import strong_config
from engine.game_state import GameState
from engine.move_generator import generate_noisy_only
from engine.pieces import Color


def _apply_random_opening(gs: GameState, rng: random.Random, plies: int) -> None:
    for _ in range(plies):
        if gs.is_terminal():
            return
        moves = gs.legal_moves()
        if not moves:
            return
        gs.apply_move(rng.choice(moves))


def _serialize(gs: GameState) -> dict:
    """One storable row for the current position (result added at game end)."""
    pieces = []
    for color in (Color.BLUE, Color.BLACK):
        for pid, (c, r) in gs.board.pieces_of(color).items():
            pieces.append([pid, c, r])
    return {
        "pieces": pieces,
        "turn": int(gs.turn),
        "noisy": bool(generate_noisy_only(gs.board, gs.turn)),
        "ply": len(gs.history),
    }


def _cmd_harvest(args: argparse.Namespace) -> None:
    t0 = time.perf_counter()
    total = 0
    with open(args.out, "a", encoding="utf-8") as out:
        for g in range(args.games):
            gs = GameState()
            gs.new_game()
            _apply_random_opening(gs, random.Random(args.seed + g),
                                  args.opening_plies)
            ai_blue = AIPlayer(Color.BLUE, 2, strong_config())
            ai_black = AIPlayer(Color.BLACK, 2, strong_config())
            rows: list[dict] = []
            for _ in range(args.max_moves):
                if gs.is_terminal():
                    break
                rows.append(_serialize(gs))
                ai = ai_blue if gs.turn == Color.BLUE else ai_black
                move = ai.get_best_move(gs, time_budget_ms=args.budget)
                if move is None:
                    break
                gs.apply_move(move)
            winner = gs.get_winner()
            result = 0.5 if winner is None else (1.0 if winner == Color.BLUE
                                                 else 0.0)
            for row in rows:
                row["result"] = result
                out.write(json.dumps(row, separators=(",", ":")) + "\n")
            out.flush()
            total += len(rows)
            if (g + 1) % 10 == 0:
                dt = time.perf_counter() - t0
                print(f"game {g + 1}/{args.games}  positions={total}  "
                      f"elapsed={dt:.0f}s", flush=True)
    print(f"done: {total} positions -> {args.out}", flush=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Jungle eval tuning")
    sub = parser.add_subparsers(dest="cmd", required=True)

    hp = sub.add_parser("harvest", help="self-play position harvesting")
    hp.add_argument("--games", type=int, default=500)
    hp.add_argument("--budget", type=int, default=120, help="per-move ms")
    hp.add_argument("--max-moves", type=int, default=200)
    hp.add_argument("--opening-plies", type=int, default=6)
    hp.add_argument("--seed", type=int, default=777000)
    hp.add_argument("--out", required=True)
    hp.set_defaults(func=_cmd_harvest)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
