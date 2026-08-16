"""Play the Rust engine against the Python engine and price the difference.

`tools/strength_harness.py` measures two *configurations* of the Python engine
against each other by constructing both in one process. That cannot work across
a language boundary, so this drives the Rust engine as a subprocess over the
small line protocol in `rust/crates/jungle-cli`, while the Python engine runs
in-process exactly as it does in the harness.

Two modes, because they answer different questions:

* ``--mode time`` gives both sides the same wall clock. This is the question the
  rewrite exists to answer, and the only mode that can see a speedup at all.
* ``--mode depth`` gives both sides the same fixed depth, which cancels the speed
  difference and asks whether the *decisions* got better or worse. A faithful
  port with its defects fixed should be somewhere at or above parity here; a
  large deficit would mean the port broke something.

Statistics come from `tools.strength_harness` so both instruments report Elo,
confidence interval and LOS the same way.

Usage::

    python -m tools.crossmatch --games 200 --budget 2000 --jobs 4
    python -m tools.crossmatch --mode depth --depth 6 --games 100 --jobs 8
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import random
import subprocess
import sys
import time
from pathlib import Path

from ai.minimax import AIPlayer
from ai.search_config import strong_config
from engine.game_state import GameState
from engine.pieces import Color
from tools.strength_harness import match_statistics

ENGINE_EXE = Path(__file__).resolve().parent.parent / "rust" / "target" / "release" / "jungle.exe"


class RustEngine:
    """A handle on one Rust engine subprocess.

    Long-lived for the duration of a game, like `AIPlayer`, so its transposition
    table and history heuristics survive across moves — throwing them away every
    move would handicap it in a way the Python side is not handicapped.
    """

    def __init__(self, exe: Path = ENGINE_EXE) -> None:
        if not exe.exists():
            raise FileNotFoundError(
                f"{exe} not found; build it with "
                f"`cargo build --release -p jungle-cli` in rust/"
            )
        self.proc = subprocess.Popen(
            [str(exe), "protocol"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )

    def _send(self, line: str) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def new_game(self) -> None:
        self._send("newgame")

    def best_move(self, gs: GameState, limit: str) -> tuple[int, int, int, int] | None:
        """Return the engine's chosen move as (fc, fr, tc, tr).

        The whole move list is replayed rather than the board being sent, so the
        engine sees the same repetition history the Python side has.
        """
        played = " ".join(
            f"{m.fc},{m.fr},{m.tc},{m.tr}" for m in gs.history if m is not None
        )
        self._send(f"position startpos{' moves ' + played if played else ''}")
        self._send(f"go {limit}")

        assert self.proc.stdout is not None
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("engine closed the pipe")
            line = line.strip()
            if line.startswith("error"):
                raise RuntimeError(f"engine rejected the position: {line}")
            if line.startswith("bestmove"):
                token = line.split()[1]
                if token == "none":
                    return None
                fc, fr, tc, tr = (int(x) for x in token.split(","))
                return (fc, fr, tc, tr)

    def close(self) -> None:
        try:
            self._send("quit")
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def _apply_random_opening(gs: GameState, rng: random.Random, plies: int) -> None:
    for _ in range(plies):
        moves = gs.legal_moves()
        if not moves or gs.is_terminal():
            return
        gs.apply_move(rng.choice(moves))


def play_one(
    rust_is_blue: bool,
    mode: str,
    budget_ms: int,
    depth: int,
    nodes: int,
    max_moves: int,
    opening_seed: int,
    opening_plies: int,
) -> Color | None:
    """Play one game; return the winning colour, or None for a draw."""
    gs = GameState()
    gs.new_game()
    _apply_random_opening(gs, random.Random(opening_seed), opening_plies)

    rust = RustEngine()
    rust.new_game()
    limit = {
        "time": f"movetime {budget_ms}",
        "depth": f"depth {depth}",
        "nodes": f"nodes {nodes}",
    }[mode]

    py_color = Color.BLACK if rust_is_blue else Color.BLUE
    python = AIPlayer(py_color, 2, strong_config())

    try:
        for _ in range(max_moves):
            if gs.is_terminal():
                break
            rust_to_move = (gs.turn == Color.BLUE) == rust_is_blue
            if rust_to_move:
                coords = rust.best_move(gs, limit)
                if coords is None:
                    break
                move = next(
                    (m for m in gs.legal_moves() if (m.fc, m.fr, m.tc, m.tr) == coords),
                    None,
                )
                if move is None:
                    raise RuntimeError(f"rust returned an illegal move {coords}")
            else:
                if mode == "time":
                    move = python.get_best_move(gs, time_budget_ms=budget_ms)
                else:
                    # Fixed depth or fixed nodes, bypassing the difficulty presets
                    # so both engines get exactly the same budget.
                    python._stop_requested = False
                    python._nodes = 0
                    python._start_time = time.perf_counter()
                    python._time_limit = 3600.0
                    python._node_limit = nodes if mode == "nodes" else None
                    python._reset_search_heuristics()
                    python._tt.new_search()
                    if mode == "nodes":
                        # Iterative deepening, so the budget is spent going as
                        # deep as it will reach rather than capped at a depth.
                        move = python._search_iterative_deepening(gs)
                    else:
                        move = python._search_fixed_depth(gs, depth)
                if move is None:
                    break
            gs.apply_move(move)
    finally:
        rust.close()

    return gs.get_winner()


def _task(args):
    (pair, swapped, mode, budget_ms, depth, nodes, max_moves, seed, plies) = args
    winner = play_one(not swapped, mode, budget_ms, depth, nodes, max_moves, seed, plies)
    return (pair, swapped, winner)


def _tally(results):
    """Count wins from the Rust engine's point of view."""
    rust_wins = py_wins = draws = 0
    for _pair, swapped, winner in results:
        if winner is None:
            draws += 1
            continue
        rust_is_blue = not swapped
        rust_won = (winner == Color.BLUE) == rust_is_blue
        if rust_won:
            rust_wins += 1
        else:
            py_wins += 1
    return rust_wins, py_wins, draws


def main() -> int:
    ap = argparse.ArgumentParser(description="Rust engine vs Python engine")
    ap.add_argument("--mode", choices=["time", "depth", "nodes"], default="time")
    ap.add_argument("--budget", type=int, default=2000, help="per-move ms (time mode)")
    ap.add_argument("--depth", type=int, default=6, help="fixed depth (depth mode)")
    ap.add_argument("--nodes", type=int, default=50_000, help="node budget (nodes mode)")
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--max-moves", type=int, default=200)
    ap.add_argument("--opening-plies", type=int, default=6)
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    pairs = max(1, args.games // 2)
    tasks = []
    for p in range(pairs):
        seed = args.seed + p
        # The same opening played twice with colours reversed, which is what
        # cancels the first-move advantage.
        for swapped in (False, True):
            tasks.append(
                (
                    p,
                    swapped,
                    args.mode,
                    args.budget,
                    args.depth,
                    args.nodes,
                    args.max_moves,
                    seed,
                    args.opening_plies,
                )
            )

    t0 = time.perf_counter()
    if args.jobs > 1:
        with multiprocessing.Pool(processes=args.jobs) as pool:
            results = pool.map(_task, tasks)
    else:
        results = [_task(t) for t in tasks]
    elapsed = time.perf_counter() - t0

    rust_wins, py_wins, draws = _tally(results)
    stats = match_statistics(rust_wins, py_wins, draws)

    limit = {"time": f"{args.budget}ms", "depth": f"depth {args.depth}",
             "nodes": f"{args.nodes} nodes"}[args.mode]
    if args.json:
        print(json.dumps({**stats, "mode": args.mode, "limit": limit, "elapsed_s": elapsed}, indent=2))
        return 0

    print(f"Cross-engine: rust vs python | mode={args.mode} limit={limit} "
          f"games={stats['games']} jobs={args.jobs} seed={args.seed}")
    print("-" * 68)
    print(f"rust wins      : {stats['a_wins']}")
    print(f"python wins    : {stats['b_wins']}")
    print(f"draws          : {stats['draws']}")
    print(f"rust score     : {stats['a_score'] * 100:.1f}%")
    print(f"Elo            : {stats['elo']:+.0f} [{stats['elo_lo']:+.0f}, {stats['elo_hi']:+.0f}]")
    print(f"LOS            : {stats['los'] * 100:.1f}%")
    if stats["elo_lo"] > 0:
        verdict = "rust is stronger (95% CI excludes parity)"
    elif stats["elo_hi"] < 0:
        verdict = "rust is WEAKER (95% CI excludes parity)"
    else:
        verdict = f"inconclusive - CI spans parity; LOS {stats['los'] * 100:.0f}%"
    print(f"verdict        : {verdict}")
    print(f"elapsed        : {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
