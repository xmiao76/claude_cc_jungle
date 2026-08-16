# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Windows desktop implementation of the Jungle (Dou Shou Qi) board game. The GUI
is Python and Pygame; **the engine is Rust**, in `rust/`, exposed to Python as a
compiled extension. Supports human-vs-AI and AI-vs-AI modes with three difficulty
levels.

The Python engine in `engine/` and `ai/` still exists and still works. It is no
longer what plays: it is the oracle the Rust engine is verified against, and the
fallback when the extension has not been built. See **Two engines, on purpose**
below before changing either.

## Common Commands

| Task | Command |
|------|---------|
| Run game (dev) | `python main.py` |
| Build the engine | `cd rust && cargo build --release -p jungle-py` then copy `rust\target\release\jungle_native.dll` to `jungle_native.pyd` |
| Run all Python tests | `pytest tests/ -v --tb=short -q` |
| Run all Rust tests | `cd rust && cargo test --release` |
| Rust tests incl. slow ones | `cd rust && cargo test --release -- --ignored` |
| Engine bench | `cd rust && cargo run --release -p jungle-cli --bin jungle -- bench 2000` |
| Perft | `cd rust && cargo run --release -p jungle-cli --bin jungle -- perft 6` |
| Rust vs Python match | `python -m tools.crossmatch --mode time --budget 500 --games 200 --jobs 4` |
| Python-only A/B | `python -m tools.strength_harness selfplay --a strong --b baseline --games 200` |
| Regenerate the golden corpus | `python -m tools.golden` |
| Build release `.exe` | `build.bat` |
| Lint | `ruff check .` and `cd rust && cargo clippy --all-targets` |

`build.bat` builds and verifies the extension, runs the Rust suite, runs the
Python suite, then packages with PyInstaller. It **fails if cargo is missing**
rather than silently packaging the Python fallback, which is ~500 Elo weaker
with nothing in the running game to say so.

## Two engines, on purpose

There are two complete implementations of the rules in this repository, and that
is deliberate. It is normally a bad idea — two rule sets drift apart and the
drift is silent — so the arrangement only holds because the agreement is
*continuously measured*, by three instruments that must all stay green:

| Instrument | What it pins | Where |
|---|---|---|
| Frozen perft counts | Move generation, exhaustively | `tests/test_perft.py`, `rust/crates/jungle-core/tests/perft.rs` |
| Golden position corpus | Legal moves, terminal status, winner on 10,000 positions | `tests/golden/positions.txt.gz` |
| Golden evaluation corpus | Static evaluation, score for score, on the same 10,000 | `tests/golden/evals.txt.gz` |

The Rust engine additionally reproduces perft(6) = 100,453,636 — cross-checked
against the Python engine, which is the only reason that number is a contract
rather than an assumption — plus perft(7) = 1,908,199,299 and the six tactical
positions to depth 8.

Move generation, measured on an idle machine: Python 327–380k leaves/s, Rust
114–135M, so about **350x**. (Earlier figures of 98–133k and "551–813x" were
taken while other jobs were running; see the note on benchmarking below.)

If you change a rule, both engines change, and all three instruments are
regenerated together (`python -m tools.golden`). If you change one and not the
other, the tests say so and name the position.

## Architecture

### The Rust engine (`rust/`)

A cargo workspace of five crates:

- **`jungle-core`** — board representation, rules, move generation, perft.
  Dependency-free. 7×9 = **63 squares fits in a `u64`**, so every terrain mask,
  adjacency set and jump path is one word. All sixteen pieces are unique, so the
  piece list is a flat `[Square; 16]` indexed by piece — no scanning, no
  duplicate handling, and the whole position is about a hundred bytes.
- **`jungle-eval`** — static evaluation, a verbatim port of `ai/evaluator.py`.
  Deliberately not retuned: a port that changes behaviour cannot be verified as
  a port.
- **`jungle-search`** — negamax PVS, transposition table, move ordering, SEE,
  quiescence, time management.
- **`jungle-cli`** — dev tooling: a line protocol for cross-engine matches,
  `bench`, `perft`. Not shipped.
- **`jungle-py`** — the PyO3 extension, built as `jungle_native.pyd`.

Measured on the Python engine's own bench positions at a 2s budget, on an
otherwise idle machine:

| Engine | depth | nodes/sec |
|---|---|---|
| this branch's Python engine (v1.3.1) | 7–8 | 14–18k |
| `main`'s Python engine (v1.5) | 8–10 | 25–27k |
| Rust | **16–17** | **2.4M** |

So roughly **+9 plies and 150x** against the engine it replaces here, and +7–8
plies against the more advanced engine on `main`.

**Benchmark on an idle machine.** An early measurement of this same Python
engine read 3,300–6,000 nps and depth 5–6, which is 2–3x low: it was taken while
other work was running. A contended bench understates the slower engine most,
because it is the one that needs the whole time budget to reach its depth.

In 200-game matches at 500ms per move, against both Python engines this
repository has had:

| Opponent | Result | Elo |
|---|---|---|
| v1.3.1 (the engine this branch replaced) | 180-0-20, 95.0% | **+512 [+447, +609]** |
| v1.5 (the engine that was on `main`) | 168-0-32, 92.0% | **+424 [+372, +495]** |

Neither Python engine won a single game out of 200. The ~88 Elo between the two
rows is the v1.4/v1.5 work, and matches what those release notes claimed for it.

**Nominal depth is not a fair currency between these two engines**, and reading
a fixed-depth result as a strength comparison will mislead you. All three of
these are the same two engines:

| Budget | Result | What it means |
|---|---|---|
| Equal **time**, 500ms, 200 games | +512 Elo [+447, +609] | how much stronger it actually is |
| Equal **nodes**, 2500, 200 games | +24 Elo [-19, +69], inconclusive | the decisions are equally good |
| Equal **depth 5**, 200 games | -49 Elo [-87, -12] | an artefact, not a defect |
| Equal **depth 3**, 100 games | +7 Elo [-57, +71], inconclusive | — |

The depth rows disagree with the node row because this engine reaches depth 5 in
about 660 nodes where the Python one needs about 5,200: the same nominal depth is
a far thinner tree, and the nodes it saves are spent going four plies deeper
instead. Equal nodes is the honest per-decision comparison and says the port is
at parity; equal time is the honest strength comparison and says it is 512 Elo
ahead. Use `crossmatch --mode nodes` or `jungle match` for the first question and
`--mode time` for the second.

### Layering

The codebase is split into four layers:

- **`main.py`** — Entry point. Initializes pygame, queries screen height to compute a dynamic `CELL_SIZE` (clamped 60–90px), registers a custom pygame event type for AI move results, then creates `Controller`.
- **`controller.py`** — State machine and main loop. Holds `AppState` (MENU, HUMAN_TURN, AI_THINKING, AI_VS_AI_THINKING, GAME_OVER). Wires `GameState`, `AIPlayer`, `Renderer`, `InputHandler`, and `Audio`. Handles the AI-as-thread pattern and defers AI start until human piece animations finish.
- **`engine/`** — Pure game logic with no pygame dependency.
  - `pieces.py` — `Animal` (1=Rat..8=Elephant) and `Color` (BLUE=0 south, BLACK=1 north) enums. Piece ID encoding: **positive = Blue, negative = Black, magnitude = rank**, 0 = empty.
  - `board.py` — `Board` stores `_grid[col][row]` (column-major) and maintains incremental Zobrist hashing via `make_move` / `unmake_move`.
  - `game_state.py` — `GameState` wraps `Board` with turn tracking, move history, and win detection. Exposes `copy()` for AI search.
  - `move_generator.py` — Generates all legal moves including precomputed river-jump tables for Lion and Tiger.
  - `rules.py` — `can_capture`, `effective_rank` (traps reduce rank to 0), `is_jump_blocked`, and `check_win`.
- **`gui/`** — Pygame rendering and input.
  - `renderer.py` — Draws board, piece sprites (with text fallback), menu, side panel, move history, animations, and capture flashes.
  - `input_handler.py` — Two-click model: click own piece to select and show legal targets, click target to move.
  - `audio.py` — Lazy-loading pygame.mixer wrapper; degrades silently if mixer unavailable (headless tests).
- **`ai/`** — Negamax alpha-beta search (principal variation search).
  - `minimax.py` — `AIPlayer` with fixed-depth (Easy/Medium) or iterative deepening (Hard). History is keyed by **side** (Blue and Black used to share entries), capped below the killer band, and carries a malus for quiet moves that failed to cut off. LMR never reduces a PV node or a **den-entry** move. Cancellable via `request_stop()`. PVS with aspiration windows; null-move pruning; reverse-futility / razoring / futility / late-move pruning at shallow depth; late-move reductions; mate-distance scoring; quiescence with SEE + delta pruning and **den-aware** noisy moves; killer / counter-move / history heuristics; a transposition table; MVV-LVA + SEE move ordering; timeout-robust iterative deepening that keeps the best move from an interrupted iteration and uses a soft time limit.
  - `evaluator.py` — **Purely static** position evaluation: material + advancement + den proximity + rat-in-water + trap control + mobility + tempo + jump-readiness + piece-square tables + den-threat/safety. Returns no mate or draw scores — the search owns terminality (see the mate-scale note below). Both sides run through one shared loop with a sign flip, which is what keeps it antisymmetric. Takes an optional `cfg` to gate individual terms.
  - `eval_tables.py` — Import-time tables for evaluation: orthogonal adjacency, and BFS **true moves-to-den** per movement class (walker / swimmer / lion / tiger). The BFS table exists because Manhattan distance walks straight through the river; it is currently off by default (measured weaker — see `search_config.py`).
  - `transposition.py` — Zobrist-keyed table with EXACT/LOWER/UPPER flags, **generation-based aging** (the table lives for a whole game, so without it a deep entry from an unreachable position holds its slot forever) and linear-pass eviction (the old policy sorted a million entries mid-move). Entries are tuples; `TTEntry` is a thin view.
  - `see.py` — Static Exchange Evaluation for capture sequences (used by quiescence and move ordering).
  - `opening_book.py` — Tiny hand-crafted opening book (Hard only, first dozen plies).
  - `search_config.py` — `SearchConfig` (immutable feature/tuning toggles) and the shared piece-value table. `strong_config()` is the shipped engine — **the strongest configuration actually measured, which is not "every flag on"**; `baseline_config()` disables everything and reproduces the original engine; `experimental_config()` turns on the four evaluation terms that were built, measured, and found to *lose* strength (their Elo numbers are recorded in the class docstring).

### Key Design Decisions

- **Piece ID encoding**: `make_piece_id(color, animal)` returns `+rank` for Blue and `-rank` for Black. Helpers `piece_id_color`, `piece_id_animal`, `piece_id_rank` decode it. This is the canonical representation across `Board`, `Move`, and the AI.
- **Move representation**: `Move` is a `NamedTuple` of `(fc, fr, tc, tr, captured)`. `captured` stores the piece ID of the taken piece (0 if none).
- **AI threading**: The AI search runs in a daemon thread so the UI stays responsive, and posts a custom pygame event (`config.AI_MOVE_EVENT_TYPE`) back to the main thread. Three things make that safe, and all three matter: the event carries a **generation token** that `_on_ai_move` checks (a result for a position we have left is discarded — applying one silently corrupts the grid, the Zobrist hash and the piece index); the thread body is wrapped in `try/except` (a crashed search used to post nothing and leave the game stuck in `AI_THINKING` forever, invisibly under `--windowed`); and `AIPlayer.request_stop()` lets the controller abort a search on Escape / new game / undo. `_on_ai_move` also validates the move against the current legal moves before applying it.
- **Engine feature config**: Every search/eval enhancement is gated by a flag on `ai/search_config.py:SearchConfig`, threaded through `AIPlayer(color, difficulty, cfg)` and into `evaluate(state, color, cfg)`. Per-instance, not global, so the harness can run two configs in one process.
- **The recorded per-flag Elo numbers are not trustworthy.** Seven of the eight
  A/B results quoted in `ai/search_config.py` were run at 40 games, where the 95%
  confidence interval is about ±100 Elo. Put back through this repo's own
  `tools.strength_harness.match_statistics`, only `use_hanging` (-255,
  [-425,-151]) excludes parity; `use_lmr_guards` and `use_tt_aging` at "+80" are
  [-16,+189], and `use_tuned_piece_values` at "-44" is [-145,+50]. So the shipped
  flag set is partly arbitrary, and several rejected ideas may well be fine. The
  *combined* effect is real and was measured properly: `strong` vs `baseline` is
  +171 Elo [+120,+229] over 200 games. Re-test individual flags before treating
  any of them as settled — with the native engine a properly powered match is
  minutes, not an overnight job, which is what made them underpowered in the
  first place.
- **Measure, do not assume.** This is the most important convention in the repo. Plausible-sounding improvements lost strength here more often than they gained it: a Rat-premium value table (-44 Elo), BFS true-distance-to-den (-70), a *corrected* jump-readiness test (-98), and static hanging-piece detection (-255, decisive) were all implemented and all measured worse than their absence. Root-move ordering by the previous iteration's scores came out at exactly 0. What did work: LMR guards (+80), TT aging (+80), side-keyed history with malus (+53). Everything that ships off is listed in `DISABLED_BY_MEASUREMENT` with its numbers in the `SearchConfig` docstring, and `test_strong_enables_every_proven_flag` fails if a flag is added without a recorded measurement. Gate any new idea behind a flag and run:
  `python -m tools.strength_harness selfplay --a strong --b <control> --games 200 --budget 250 --jobs 8`
  Read the verdict line, not the percentage: at 40 games one standard error is about 8 points, so a 55% result is not a result.
- **Mate scale (one scale only)**: `evaluate` never returns a terminal score. Mate scores come from the search as `±(_MATE - ply)`, and `_MATE < _INF` where `_INF` is only the alpha/beta sentinel. `evaluate` used to return `±_INF` for a decided position, which is *larger* than any real mate — it outranked every mate, broke mate-distance preference, and wrote out-of-window scores into the TT. Quiescence therefore owns its own no-legal-moves and 50-move checks.
- **Piece values live in one place**: `ai/search_config.py:piece_values(cfg)`. Evaluation, SEE and quiescence delta pruning must all read the same table or they disagree about what a capture is worth. SEE also orders recapturers by *value*, not rank — with a non-linear table, rank order is no longer value order.
- **Eval symmetry invariant (do not break)**: `evaluate(BLUE) == -evaluate(BLACK)` for any position (enforced by tests in `tests/test_evaluator.py`). Every per-piece positional term must be computed from the *piece's own color* (added for own pieces, subtracted for opponent pieces) — never from the evaluating side's perspective. The PST is also column-symmetric so the symmetric start position evaluates to 0 (modulo the side-to-move `tempo` bonus). Jungle has no "check"; the tactical analog is **den entry**, which is why quiescence treats den-entry moves as noisy and the eval has a den-threat term.
- **Animation deferral**: After a human move, `_pending_ai_after_anim` is set to `True`. The AI thread is not started until `renderer.has_active_animation(tick_ms)` returns `False`, so the player sees their piece finish sliding before the AI responds.
- **Board flip is visual-only**: `flipped` lives in `Controller` and `Renderer` and affects only how squares are mapped to pixels and how mouse coordinates map back to board squares (`pixel_to_board`). The engine (`Board`, `GameState`, `AI`) always sees an unflipped board. Blue always starts at row 8, Black at row 0.
- **Asset paths**: `config.asset_path(relative)` resolves paths correctly in both development and when running as a PyInstaller `--onefile` bundle (uses `sys._MEIPASS`).
- **Rat/water boundary rule**: A piece in water is invulnerable to attacks from land pieces, and vice versa, *except* Rat vs Rat on the same terrain type. Rat on land can capture Elephant on land. See `rules.py:can_capture`.
- **Trap rule — defence only**: `can_capture` applies the trap's rank-0 effect to the **defender** and never to the attacker. A piece standing in the enemy's traps can be taken by any adjacent enemy piece (Elephant included, which overrides the Elephant-cannot-take-Rat exception), but it still attacks at its full rank: vulnerable, not disarmed. The order of the checks in `can_capture` matters — water boundary, then defender-trapped, then the rank comparison with the Rat exceptions. This was the `knowIssue.txt` defect: the Elephant-vs-Rat rejection sat *before* the trap check and so never saw it. The GUI marks a trapped piece with a red rank-0 badge, because nothing on the board used to indicate it.
- **River jumps**: the river is columns {1,2} and {4,5} across rows {3,4,5}, so a **horizontal** (column-axis) leap crosses **2** river squares and a **vertical** (row-axis) leap crosses **3**. Lion makes both; **Tiger makes the horizontal 2-square leap only** (`_can_jump` allows Tiger when `dc != 0`). A rat of *either* colour on any water square along the path blocks it. Jumps are precomputed in `_build_jump_table()` at import time, and the geometry is asserted in `rust/crates/jungle-core/src/bitboard.rs`.

### Testing

Tests live in `tests/` and use pytest; configuration is in `pyproject.toml`. The engine layer needs no display. Build arbitrary positions with `tests.helpers.make_gs` — **never by writing `Board._grid` directly**, which leaves `Board.hash` at 0 and aliases every hand-built position to the same TT key, and lets two pieces of the same animal coexist so the grid and the piece index disagree. `Board.place` is the supported way in.

Two safety nets are worth knowing before changing the engine:

- **`tests/test_perft.py`** — frozen leaf counts for the start position and six tactical positions. Any change to move generation, `make_move`/`unmake_move` or the rules must leave these identical; a change means a rules change, and it has to be deliberate. Localise a mismatch with `tools.perft.perft_divide`, or `python -m tools.strength_harness perft --depth 4 --divide`.
- **`tests.helpers.assert_board_consistent`** — asserts the grid, the piece-position index and the incremental Zobrist hash all agree. This is the invariant to lean on when touching the board representation.

## File Reference

| File | Responsibility |
|------|----------------|
| `main.py` | pygame init, window sizing, custom event registration |
| `controller.py` | game loop, state machine, AI thread orchestration |
| `config.py` | constants, colors, AI depth settings, asset path helper |
| `engine/pieces.py` | enums, piece ID encoding, starting positions |
| `engine/board.py` | grid state, incremental Zobrist hashing, make/unmake |
| `engine/game_state.py` | turn, history, legal-move cache, win detection |
| `engine/move_generator.py` | all legal moves, noisy (capture + den-entry) moves, river-jump precomputation |
| `engine/rules.py` | capture rules, effective rank, jump blocking, win check |
| `ai/minimax.py` | negamax PVS, pruning (NMP/RFP/razor/futility/LMP/LMR), iterative deepening, MVV-LVA+SEE ordering, quiescence |
| `ai/evaluator.py` | static position evaluation (material, positional, PST, den-threat) |
| `ai/transposition.py` | Zobrist-keyed TT |
| `ai/see.py` | static exchange evaluation |
| `ai/opening_book.py` | hand-crafted opening book (Hard) |
| `ai/search_config.py` | `SearchConfig` feature toggles, shared piece-value table; `strong_config()` / `baseline_config()` / `experimental_config()` |
| `ai/eval_tables.py` | import-time adjacency and BFS moves-to-den tables |
| `gui/renderer.py` | all drawing: board, pieces, UI, animations |
| `gui/input_handler.py` | mouse → board action translation |
| `gui/audio.py` | sound effects with mute toggle |
| `generate_assets.py` | procedural art generation for pieces/tiles |
| `ai/native.py` | the native engine wearing the `AIPlayer` interface, plus `make_ai_player` (native, falling back to Python) and the `AIEngine` protocol |
| `rust/crates/jungle-core/` | rules, bitboards, move generation, Zobrist, perft — dependency-free |
| `rust/crates/jungle-eval/` | static evaluation, ported verbatim from `ai/evaluator.py` |
| `rust/crates/jungle-search/` | negamax PVS, transposition table, ordering, SEE, quiescence, time management |
| `rust/crates/jungle-cli/` | dev-only: line protocol for cross-engine play, bench, perft |
| `rust/crates/jungle-py/` | PyO3 bindings, built as `jungle_native.pyd` |
| `tools/golden.py` | generates the golden position and evaluation corpora |
| `tools/crossmatch.py` | dev-only: Rust vs Python matches, at equal time or equal depth |
| `tools/strength_harness.py` | dev-only: self-play A/B match with Elo/CI/LOS, node/depth bench, perft (not bundled) |
| `tools/perft.py` | dev-only: exhaustive leaf counts — the move-generation contract |
| `tools/positions.py` | dev-only: hash-correct position builders shared by tests and harness |
| `tests/helpers.py` | shared fixtures plus `assert_board_consistent` (grid / index / hash agree) |
| `build.bat` | Windows build script (test → PyInstaller → release) |
