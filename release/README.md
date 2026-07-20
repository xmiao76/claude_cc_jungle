# JUNGLE — Dou Shou Qi

**Version 2.2 · Windows Desktop**

A polished desktop version of the classic Chinese board game **Jungle**
(*Dou Shou Qi* / 斗兽棋, "Battle of the Animals") with a built-in AI opponent,
played on a visual 7×9 board.

---

## Authorship — model & code agent

This application was designed and implemented **entirely by an AI coding
agent**. Every line of source code, all artwork (piece sprites, terrain tiles,
window icon), all sound effects, the automated test suite, and the packaging
were generated programmatically. No third-party code or assets were used.

- **AI model:** Claude **Opus 4.8** (1M-context), model id `claude-opus-4-8`
- **Code agent:** **Claude Code** — Anthropic's official command-line coding agent
- **Build:** fresh, from-scratch implementation completed on **2026-07-19**

---

## How to launch

Double-click **`jungle_game.exe`**. No installation and no Python required.

The window opens on the main menu. It is DPI-aware and renders crisply at any
Windows display-scaling setting (100 % / 125 % / 150 % / 175 %). The window is
resizable — drag any edge and the whole board and panel scale uniformly
(letterboxed to preserve proportions) with no clipping or distortion.

---

## The game

Jungle is a two-player strategy game on a 7-wide × 9-tall board. You control
one side; the computer controls the other. **Blue always moves first**; from
the menu you choose whether **you** or the **AI** takes the Blue side.

### How to win

1. **Den dash** — move any of your pieces into the opponent's **den** (the
   crowned square on the far side), **or**
2. **Capture** every one of the opponent's pieces.

(A player with no legal move loses; repetition or 50 moves with no capture is a
draw.)

### Pieces, strongest to weakest

    Elephant (8) > Lion (7) > Tiger (6) > Leopard (5) > Wolf (4) > Dog (3) > Cat (2) > Rat (1)

Each token shows the animal's **name**; its rank is its place in the order above
(Elephant highest, Rat lowest). A piece captures an enemy of **equal or lower**
rank on an adjacent square — with one famous exception:

- **The Rat (1) can capture the Elephant (8).** (And the Elephant may **not**
  capture the Rat.)

### Terrain

| Tile | Meaning |
|------|---------|
| **Green** | Land — normal movement. |
| **Blue (water)** | River — only the **Rat** may enter it. |
| **Brown (X)** | Trap — an **enemy** piece standing in your trap drops to rank 0 and can be captured by *any* adjacent piece of yours. |
| **Gold (crown)** | Den — move here to win. You may **never** enter your own den. |

### Special movement — river jumping

- **Lion** may leap **either** river crossing:
  - the long crossing over the **3 river rows** — landing **4 rows** away
    (the prompt's *"horizontal"* lion jump), and
  - the short crossing over the **2 river columns** — landing **3 columns**
    away (the prompt's *"vertical"* jump).
- **Tiger** may leap **only** the short crossing — **3 columns**, over the 2
  river columns. The Tiger cannot make the 4-row leap.
- A **Rat sitting anywhere on the water** along the leap's path **blocks** the
  jump.

### Rat & water rules

- A Rat in the water cannot capture (or be captured by) a piece on land.
- A Rat in the water is safe from all land pieces.
- A Rat may only capture another Rat when both are on the same kind of terrain.

---

## Controls

| Input | Action |
|-------|--------|
| Click your piece | Select it (gold outline). Green dots/rings show its legal moves. |
| Click a green marker | Move there. |
| Click elsewhere | Deselect. |
| **U** | Undo (takes back your move **and** the AI's reply). |
| **F** | Flip the board view (display only — never changes the game). |
| **M** | Toggle sound. |
| **Esc** | Return to the main menu. |

The side panel also has on-screen **Flip**, **Undo**, and **Sound** buttons,
plus the current turn, piece counts, move number, mode, and difficulty.

---

## Menu options

- **Play: Human vs AI** — you play one side against the computer.
- **Watch: AI vs AI** — the computer plays both sides (great to watch).
- **First move: Human / AI** — who takes the first (Blue) move. Works together
  with the board-flip view.
- **Difficulty:**
  - **Easy** — 3-ply search, instant.
  - **Medium** — 5-ply search, fast.
  - **Hard** — time-managed search (~2 s per move); plays a strong game. The
    engine uses principal-variation search, null-move pruning, late-move
    reductions, a history heuristic, aspiration windows, and a den-threat
    extension (v2.1, ~+68 Elo in self-play at a deep search budget). v2.2 makes
    the evaluation incremental, so the engine runs ~1.6x faster and searches a
    full ply deeper in the same time (that extra search is worth ~+97 Elo in
    time-odds self-play).
- **Board view: Normal / Flipped** — rotate the board 180° for display only.

---

## Notes

- The AI runs on a background thread, so the window stays responsive while it
  thinks (a spinner shows in the side panel).
- Board flip is purely visual: it never changes whose turn it is, which side
  you control, or the position.
- After the game ends, choose **Play again** or **Quit**.

## Rules reference

Standard rules: <https://en.wikipedia.org/wiki/Jungle_(board_game)>

### Rule interpretations used in this implementation

- River jumping: **Lion** leaps both crossings (4-rows and 3-columns);
  **Tiger** leaps only the 3-column crossing; a Rat in the water path blocks it.
- A Rat in the water cannot capture, be captured by, or be reached across the
  water/land boundary by land pieces.
- An enemy piece in one of your traps has rank 0 (any adjacent piece may take
  it — including an Elephant taking a trapped Rat).
- Entering your own den is illegal; entering the enemy den wins instantly.
- Threefold repetition or 50 moves without a capture is a draw; a side with no
  legal move loses.
