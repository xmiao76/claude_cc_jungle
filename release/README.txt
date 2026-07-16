JUNGLE - THE BOARD GAME
=======================
Version 1.5 | Windows Desktop


AUTHORSHIP
----------
Designed and implemented by AI coding agents via Claude Code (Anthropic's
official command-line coding agent). The architecture, gameplay logic, AI
engine, GUI, automated tests, and packaging were all generated
programmatically; no third-party code was incorporated.
  Initial generation  : 2026-04-23 (Claude Opus 4.8, model "claude-opus-4-8",
                        max effort, via Claude Code)
  1.2-1.3 engine work : 2026-06-19 (Claude Opus 4.8, max effort, via Claude Code)
  1.4 engine update   : 2026-07-15 (Claude Fable 5, model "claude-fable-5",
                        max effort, via Claude Code)
  1.5 rules fix +
  engine update       : 2026-07-15 (Claude Fable 5, model "claude-fable-5",
                        max effort, via Claude Code)

WHAT'S NEW IN 1.5
-----------------
  Rules fix:
  - An enemy piece standing in one of your traps can now be captured by ANY
    adjacent piece — as the rules always stated. Previously the Elephant
    refused to capture a trapped Rat (the Rat-beats-Elephant exception
    wrongly outranked the trap rule).

  Engine (stronger than the shipped 1.4, measured honestly):
  - Rebuilt board internals ("flat board"): the engine examines positions
    about 1.6x faster than the 1.4 release (2.5x the original 1.3 engine).
    Speed is strength in timed play: against the 1.4 engine running at its
    original speed (a time-odds simulation, conservatively scaled), 1.5
    scored 59.2% over 200 games. Feature-for-feature at EQUAL speed the new
    search/eval ideas add only a few Elo (51.5% over 400 games) — this
    release's gain is mostly the speed.
  - Against the built-in 1.3 engine at equal time, 1.5 scores 59.0%
    (1.4 scored 56.5% in the same test).
  - Smarter search: a finer-grained table decides how deeply each move is
    re-examined (informed by each move's track record), pruning tightens
    automatically in worsening positions, and two-move reply patterns are
    remembered for move ordering.
  - The evaluation now spots hanging pieces — an undefended piece attacked
    by an adjacent stronger enemy is scored as being in danger.
  - A self-play tuning pipeline (position harvesting + logistic weight
    fitting) ships in the codebase; its first run showed the hand-tuned
    weights are already near a local optimum, so they ship unchanged.
  - The 1.4 engine joins 1.3 as a frozen built-in sparring partner ("v14")
    so future changes stay measurable against every past release.

WHAT'S NEW IN 1.4
-----------------
  The AI engine is measurably stronger than 1.3 (self-play at equal time:
  56.5% score over 400 games against the built-in 1.3 engine, ~+45 Elo,
  consistent across two independent 200-game matches):
  - About 1.7x faster search: a dedicated capture generator and a leaner
    evaluation let the engine look a full move deeper in the same time.
  - Fixed a subtle scoring bug that made the engine treat winning lines as
    draws whenever they passed through a position it had seen once before.
  - Smarter transposition table: it now remembers evaluations, ages out
    stale entries between moves, and no longer stalls mid-move when it
    fills up during long games.
  - Better time management: the engine banks unused thinking time on easy
    moves and spends it when the position turns critical (Hard may briefly
    think up to ~3s on a difficult move; the average stays ~2s).
  - The 1.3 engine ships inside the code as a frozen sparring partner
    ("v13") so every future change is measured against the previous release.

WHAT'S NEW IN 1.3
-----------------
  The AI engine plays noticeably stronger than 1.2:
  - Sharper move ordering (MVV-LVA + Static Exchange Evaluation) and extra
    search pruning (reverse-futility, razoring, futility, and late-move
    pruning) cut the work per position by roughly a third, so the engine
    searches about one ply deeper in the same time budget.
  - Smarter time management: it keeps the best line found when a deep search is
    interrupted and skips iterations it cannot finish in the time budget.
  - Piece-square tables: a better sense of which squares matter, especially
    control of the central file leading to the den.
  - Den-aware tactics: the engine now spots winning and losing "den dashes" at
    the search horizon and defends its own den approaches more reliably.
  - A self-play strength harness was added to the codebase to measure every
    engine change head-to-head against the previous version.

WHAT'S NEW IN 1.2
-----------------
  - Stronger AI engine: principal-variation search with null-move pruning and
    late-move reductions; iterative deepening reaches deeper inside the same
    time budget.
  - Mate-distance scoring: the AI now prefers faster wins and longer losses.
  - Static Exchange Evaluation: avoids losing trades the old AI fell for.
  - Repetition and 50-move draw recognition: no more endless shuffling.
  - Richer position evaluation: mobility, defenders, jump-readiness, river
    blockades, and tempo all factor in.
  - Tiny opening book on Hard difficulty for sharper early play.

WHAT'S NEW IN 1.1
-----------------
  - Undo button (and "U" hotkey): take back your last move and the AI's reply.
  - Move history panel: see the last 8 moves at a glance.
  - Smooth piece animations when moves are played.
  - Sound effects for moves, captures, and wins (toggle with the Sound button or "M").
  - Difficulty hint on the main menu so you know what each level does.
  - Smarter AI: quiescence search at the depth horizon, killer-move and history
    heuristics for sharper move ordering, depth-prefer transposition table.

HOW TO LAUNCH
-------------
Double-click jungle_game.exe.
No installation required. No Python needed.


THE GAME
--------
Jungle (Dou Shou Qi / 斗兽棋) is a classic two-player Chinese strategy board game
played on a 7x9 grid. You play as Blue (bottom). The AI plays as Black (top).
Blue moves first.


OBJECTIVE
---------
Win by either:
  1. Moving any of your pieces into the opponent's den (the crown square at the top),
  2. Capturing all 8 of the opponent's pieces.


PIECES (strongest to weakest)
------------------------------
  Elephant (8) > Lion (7) > Tiger (6) > Leopard (5) >
  Wolf (4) > Dog (3) > Cat (2) > Rat (1)

The number shown on each piece is its rank.

SPECIAL: The Rat (rank 1) can capture the Elephant (rank 8).


TERRAIN
-------
  Green squares   : Normal land
  Blue squares    : Rivers — only the Rat can swim in rivers
  Brown squares   : Traps — any enemy piece entering your trap has rank 0 (capturable by anyone)
  Gold squares    : Dens — move any piece here to win (cannot enter your own den)


SPECIAL MOVEMENT RULES
-----------------------
  Lion   : Can jump both river crossings - the 2-square horizontal AND the 3-square vertical (blocked by a Rat in the river path)
  Tiger  : Can jump only the 2-square horizontal river crossing (blocked by a Rat in the river path)
  Rat    : The only piece that can swim (enter river squares)
           A Rat in the river cannot capture an Elephant on land
           A Rat on land cannot capture a Rat that is in the river
           A Rat in the river cannot be attacked by any land piece


CONTROLS
--------
  Click your piece     - Selects the piece (gold border appears)
  Green dots           - Show all legal move destinations
  Click a green dot    - Move the selected piece there
  Click elsewhere      - Deselect the piece
  ESC key              - Return to the main menu
  U key                - Undo (rolls back your move and the AI's reply)
  M key                - Toggle sound on/off


MAIN MENU
---------
  Human vs AI      - Play against the computer (you are Blue)
  Watch AI vs AI   - Watch two AI players compete automatically
  Difficulty       - Cycle through Easy / Medium / Hard (click to change)


DIFFICULTY LEVELS
-----------------
  Easy    - Looks 2 moves ahead. Good for learning.
  Medium  - Looks 4 moves ahead. A real challenge.
  Hard    - Time-managed search (~2s per move on average; it saves up unused
            time and may think up to ~3s on critical moves). Plays a strong
            strategic game.


AI VS AI MODE
-------------
Select "Watch AI vs AI" from the main menu.
Both sides play automatically at the selected difficulty level.
You can watch the game and return to the menu with ESC at any time.


NOTES
-----
  - The AI runs in a background thread — the window stays responsive while it thinks.
  - A spinning indicator appears in the side panel while the AI is computing its move.
  - The side panel shows the current turn, piece counts, and move number.
  - After the game ends, click "Play Again" to restart or "Quit" to exit.
  - Press ESC at any time during a game to return to the main menu.


RULES REFERENCE
---------------
Full rules are available at: https://en.wikipedia.org/wiki/Jungle_(board_game)

Rule interpretations used in this implementation:
  - Lion can jump both river crossings (2-square horizontal and 3-square vertical); Tiger can jump only the 2-square horizontal crossing
  - Rat in water cannot capture Elephant on land (and vice versa)
  - Rat in water cannot be captured by land pieces
  - Own traps do NOT reduce your own pieces' rank
  - Entering your own den is illegal
  - Den entry wins immediately
  - Player with no legal moves loses
