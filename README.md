# Jungle — Dou Shou Qi

A polished Windows desktop version of the classic board game **Jungle**
(*Dou Shou Qi*, "Battle of the Animals"), with a built-in AI, human-vs-AI and
AI-vs-AI play, animated pieces, sound, and a packaged Windows `.exe`.

Built from scratch in **Python 3.12 + Pygame**. All source code and assets
(sprites, tiles, icon, sounds) are original and generated in code.

## Quick start

```bat
pip install -r requirements.txt
python generate_assets.py     REM create art + sounds under gui/assets/
python main.py                REM play
python -m pytest tests\ -q    REM run the test suite
build.bat                     REM build release\jungle_game.exe (+ zip)
```

## Highlights

- Correct, tested implementation of the standard ruleset (river jumps, traps,
  dens, the Rat/Elephant exception, draws).
- Negamax α-β engine with iterative deepening and three difficulty levels; the
  v2.1 search (PVS, null-move pruning, late-move reductions, history heuristic,
  aspiration windows, den-threat extension) searches several plies deeper and is
  ~+68 Elo stronger in self-play. Every strength change is measured by
  node-limited self-play (`tools/strength_harness.py`), never assumed.
- Attractive board: distinct terrain, animal sprites, selection highlights,
  legal-move indicators, capture feedback, turn display, and win/loss messaging.
- Choose who moves first (human or AI); flip the board view (display only).
- DPI-aware, resizable window that renders crisply across Windows resolutions
  and display-scaling settings.

## Documentation

- Player guide, controls, and the model/code-agent statement:
  [`release/README.md`](release/README.md)
- Developer notes (architecture, commands, rules): [`CLAUDE.md`](CLAUDE.md)
- Original task/spec: [`prompt.md`](prompt.md)

Built by **Claude Opus 4.8** via **Claude Code** (Anthropic's official CLI).
