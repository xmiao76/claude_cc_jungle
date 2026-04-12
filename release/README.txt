JUNGLE - THE BOARD GAME
=======================
Version 1.0 | Windows Desktop

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
  Lion   : Can jump over an entire river horizontally OR vertically (blocked if a Rat is in the river)
  Tiger  : Can jump over an entire river vertically only (blocked if a Rat is in the river)
  Rat    : The only piece that can swim (enter river squares)
           A Rat in the river cannot capture an Elephant on land
           A Rat on land cannot capture a Rat that is in the river
           A Rat in the river cannot be attacked by any land piece


CONTROLS
--------
  Mouse only.

  Click your piece     - Selects the piece (gold border appears)
  Green dots           - Show all legal move destinations
  Click a green dot    - Move the selected piece there
  Click elsewhere      - Deselect the piece
  ESC key              - Return to the main menu


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
  - Lion can jump both horizontally and vertically
  - Tiger can only jump vertically
  - Rat in water cannot capture Elephant on land (and vice versa)
  - Rat in water cannot be captured by land pieces
  - Own traps do NOT reduce your own pieces' rank
  - Entering your own den is illegal
  - Den entry wins immediately
  - Player with no legal moves loses
