JUNGLE - THE BOARD GAME
=======================
Version 1.3.1 | Windows Desktop


AUTHORSHIP
----------
Designed and implemented by AI coding agents via Claude Code (Anthropic's
official command-line coding agent). The architecture, gameplay logic, AI engine,
GUI, automated tests, and packaging were all generated programmatically; no
third-party code was incorporated.
  Initial generation   : 2026-04-23 (Claude Opus 4.8, model "claude-opus-4-8",
                         max effort, via Claude Code)
  1.2-1.3 engine work  : 2026-06-19 (Claude Opus 4.8, max effort, via Claude Code)
  1.3.1 rules + engine : 2026-07-24 (Claude Opus 5, model "claude-opus-5",
                         1M-context variant, via Claude Code)

WHAT'S NEW IN 1.3.1
-------------------
  A rules correction and a measurably stronger engine.

  - FIXED: your Elephant could not capture an enemy Rat that had walked into
    your own trap. A piece in your trap has rank 0 and must be capturable by
    anything next to it, but the Elephant-cannot-eat-Rat exception was applied
    first and never consulted the trap. Every other animal was unaffected.
    The same bug made it worse than a missed capture: the trapped Rat could
    still eat the Elephant that could not eat it.
  - A trapped piece is now marked on the board: its rank badge turns red and
    reads 0, and its square is outlined, so you can see it has lost its rank.
  - Capture targets are easier to see. The green marker for a square that holds
    an enemy piece is now drawn on top of that piece instead of behind it.
  - The AI plays substantially stronger, and searches about a ply deeper in the
    same time. Measured by self-play at an equal time budget:
      +76 Elo against this same engine with 1.3.1's search changes switched off
        (60 games), and
      +182 Elo against the engine with all optional enhancements disabled
        (100 games, 95% confidence interval +115 to +264).
    Several of the fixes below apply unconditionally, so they improve both sides
    of those comparisons and are not captured by either figure.
      Behind that: the quiescence search was throwing away free material because
      it compared a piece's rank against a centipawn margin; an evaluation term
      was mathematically guaranteed to be zero in every position; two conflicting
      mate scales meant a detected win could outrank a real forced win; late-move
      reductions were reducing the game-winning den entry; and the transposition
      table never expired stale entries.
  - Easy and Medium can no longer stall the window on a difficult position.
  - Fixed a rare crash-and-hang: if you pressed Escape or restarted while the AI
    was thinking, its result could be applied to the new position and corrupt
    the board. A crashed search also used to leave the game thinking forever.
  - The download is half the size (15 MB, was 29 MB): the packaging step was
    bundling every image and sound three times.
  - The window and executable now show the game's icon.

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
                    A piece standing in a trap shows a red 0 badge and an outlined square
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
  Green outlined square- A legal destination holding an enemy piece you can capture
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
  Easy    - Looks 3 moves ahead. Good for learning.
  Medium  - Looks 5 moves ahead. A real challenge.
  Hard    - Thinks for up to 2 seconds per move and searches as deep as it can
            in that time. Plays a strong strategic game.

  (Easy and Medium are fixed-depth, so they respond almost instantly. The
   figures above are the search depths the game actually uses.)


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
  - A trap reduces rank for DEFENCE only: a piece standing in an enemy trap can
    be captured by any adjacent enemy piece (including an Elephant taking a Rat),
    but it still attacks at its full rank
  - Entering your own den is illegal
  - Den entry wins immediately
  - Player with no legal moves loses
