JUNGLE - THE BOARD GAME
=======================
Version 1.2 | Windows Desktop


AUTHORSHIP
----------
Designed and implemented by an AI coding agent (Anthropic's Claude Opus 4.7
via Claude Code). The architecture, gameplay logic, AI engine, GUI, automated
tests, and packaging were all generated programmatically; no third-party code
was incorporated. Initial generation: 2026-04-23.

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
  Hard    - Uses up to 2-second search. Plays a strong strategic game.


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
