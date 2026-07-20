"""Application controller: the state machine that ties input, rendering, audio,
and the AI together.

States: ``menu`` -> ``playing`` -> ``over``. The AI runs on a background thread
so the window stays responsive; each computation carries a token so results
from a superseded search (after undo / return-to-menu) are ignored.
"""

from __future__ import annotations

import logging
import threading

import pygame

import config
from ai.minimax import AIPlayer
from engine.game_state import GameState
from engine.pieces import Color
from gui.audio import Audio
from gui.input_handler import InputHandler
from gui.renderer import Renderer

BLUE = int(Color.BLUE)
BLACK = int(Color.BLACK)
ROWS = config.ROWS

_log = logging.getLogger(__name__)


class Controller:
    def __init__(self, surface: pygame.Surface) -> None:
        self.surface = surface
        self.renderer = Renderer(surface)
        self.audio = Audio()
        self.input = InputHandler()
        self.gs = GameState()

        self.state = "menu"
        self.mode_ava = False
        self.player_first = True
        self.human_color = BLUE
        self.flipped = False
        self.difficulty = 1                 # Medium by default

        self._ai_blue: AIPlayer | None = None
        self._ai_black: AIPlayer | None = None
        self._ai_thinking = False
        self._ai_token = 0

        self._anim: dict | None = None
        self._capture_flash: tuple[int, int] | None = None
        self._last_move = None
        self.running = True

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        clock = pygame.time.Clock()
        while self.running:
            tick = pygame.time.get_ticks()
            if not self._handle_events(tick):
                break
            self._update(tick)
            self._render(tick)
            pygame.display.flip()
            clock.tick(config.FPS)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _handle_events(self, tick: int) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == "menu":
                        return False
                    self._go_to_menu()
                elif event.key == pygame.K_u:
                    self._try_undo()
                elif event.key == pygame.K_m:
                    self.audio.toggle_mute()
                elif event.key == pygame.K_f:
                    self._toggle_flip()
            elif event.type == config.AI_MOVE_EVENT_TYPE:
                self._on_ai_result(event, tick)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos, tick)
        return True

    def _handle_click(self, pos: tuple[int, int], tick: int) -> None:
        if self.state == "menu":
            self._menu_click(pos)
            return
        if self.state == "over":
            if self.renderer.over_buttons.get("again") and \
                    self.renderer.over_buttons["again"].collidepoint(pos):
                self._start_game(self.mode_ava)
            elif self.renderer.over_buttons.get("quit") and \
                    self.renderer.over_buttons["quit"].collidepoint(pos):
                self.running = False
            return

        # playing: side-panel buttons first
        b = self.renderer.buttons
        if b.get("flip") and b["flip"].collidepoint(pos):
            self._toggle_flip()
            return
        if b.get("undo") and b["undo"].collidepoint(pos):
            self._try_undo()
            return
        if b.get("mute") and b["mute"].collidepoint(pos):
            self.audio.toggle_mute()
            return

        # board interaction only on the human's turn, when idle
        if self.mode_ava or self._ai_thinking or self._anim is not None:
            return
        if self.gs.to_move != self.human_color:
            return
        move = self.input.handle_click(pos[0], pos[1], self.gs, self.human_color, self.flipped)
        if move is not None:
            self._apply_move(move, tick)

    def _menu_click(self, pos: tuple[int, int]) -> None:
        mb = self.renderer.menu_buttons
        if mb.get("hva") and mb["hva"].collidepoint(pos):
            self._start_game(ava=False)
        elif mb.get("ava") and mb["ava"].collidepoint(pos):
            self._start_game(ava=True)
        elif mb.get("first") and mb["first"].collidepoint(pos):
            self.player_first = not self.player_first
        elif mb.get("difficulty") and mb["difficulty"].collidepoint(pos):
            self.difficulty = (self.difficulty + 1) % 3
        elif mb.get("flip") and mb["flip"].collidepoint(pos):
            self._toggle_flip()

    # ------------------------------------------------------------------
    # Game flow
    # ------------------------------------------------------------------

    def _start_game(self, ava: bool) -> None:
        self.mode_ava = ava
        self.gs.new_game()
        self.input.reset()
        self._ai_token += 1
        self._ai_thinking = False
        self._anim = None
        self._capture_flash = None
        self._last_move = None
        self._ai_blue = AIPlayer(BLUE, self.difficulty)
        self._ai_black = AIPlayer(BLACK, self.difficulty)
        # Blue always moves first; player_first decides who controls Blue.
        self.human_color = BLUE if self.player_first else BLACK
        self.state = "playing"

    def _go_to_menu(self) -> None:
        self.state = "menu"
        self._ai_token += 1        # cancel any in-flight AI result
        self._ai_thinking = False
        self._anim = None
        self._capture_flash = None
        self.input.reset()

    def _toggle_flip(self) -> None:
        self.flipped = not self.flipped
        self.renderer.flipped = self.flipped

    def _current_mover_is_ai(self) -> bool:
        if self.mode_ava:
            return True
        return self.gs.to_move != self.human_color

    def _apply_move(self, move, tick: int) -> None:
        code = self.gs.board.sq[move.frm]
        self._last_move = move
        fx, fy = self.renderer.cell_topleft(move.frm // ROWS, move.frm % ROWS)
        tx, ty = self.renderer.cell_topleft(move.to // ROWS, move.to % ROWS)
        self._anim = {"code": code, "dst": move.to, "from": (fx, fy),
                      "to": (tx, ty), "x": fx, "y": fy, "start": tick}
        if move.captured != 0:
            self.audio.play("capture")
            self._capture_flash = (move.to, tick)
        else:
            self.audio.play("move")
        self.input.reset()
        self.gs.make_move(move)

    def _finish_anim(self) -> None:
        self._anim = None
        if self.gs.game_over:
            self.state = "over"
            if self.gs.winner() is not None:
                self.audio.play("win")

    def _start_ai(self, tick: int) -> None:
        self._ai_thinking = True
        token = self._ai_token
        ai = self._ai_blue if self.gs.to_move == BLUE else self._ai_black
        snapshot = self.gs.clone()

        def worker() -> None:
            move = None
            try:
                move = ai.choose_move(snapshot)
            except Exception:
                # A search bug must not crash the UI; log it and let the main
                # thread fall back to a legal move (see _on_ai_result).
                _log.exception("AI search failed; falling back to a legal move")
                move = None
            try:
                pygame.event.post(pygame.event.Event(
                    config.AI_MOVE_EVENT_TYPE, move=move, token=token))
            except Exception:
                # If the event can't be posted, _ai_thinking would stay set; ESC
                # (-> _go_to_menu) clears it, which is the intended escape hatch.
                _log.exception("Failed to post AI move event")

        threading.Thread(target=worker, daemon=True).start()

    def _on_ai_result(self, event, tick: int) -> None:
        self._ai_thinking = False
        if getattr(event, "token", None) != self._ai_token:
            return                      # stale result from a superseded search
        if self.state != "playing" or self._anim is not None or self.gs.game_over:
            return
        if not self._current_mover_is_ai():
            return
        move = getattr(event, "move", None)
        if move is None:                # safety fallback
            legal = self.gs.legal_moves()
            if not legal:
                return
            move = legal[0]
        self._apply_move(move, tick)

    def _try_undo(self) -> None:
        if self.mode_ava or self._ai_thinking or self._anim is not None:
            return
        if self.state not in ("playing", "over"):
            return
        if not self.gs._history:
            return
        self._ai_token += 1            # cancel any pending AI search
        # Roll back to the human's turn: undo the AI reply and the human move.
        undone = 0
        while self.gs._history and undone < 2:
            self.gs.undo_move()
            undone += 1
            if self.gs.to_move == self.human_color and not self.gs.game_over:
                break
        self.state = "playing"
        self._last_move = None
        self._capture_flash = None
        self.input.reset()

    # ------------------------------------------------------------------
    # Update + render
    # ------------------------------------------------------------------

    def _update(self, tick: int) -> None:
        if self._anim is not None:
            p = min(1.0, (tick - self._anim["start"]) / config.MOVE_ANIM_MS)
            ease = p * p * (3 - 2 * p)      # smoothstep
            fx, fy = self._anim["from"]
            tx, ty = self._anim["to"]
            self._anim["x"] = fx + (tx - fx) * ease
            self._anim["y"] = fy + (ty - fy) * ease
            if p >= 1.0:
                self._finish_anim()
            return

        if self.state == "playing" and not self.gs.game_over \
                and not self._ai_thinking and self._current_mover_is_ai():
            self._start_ai(tick)

    def _render(self, tick: int) -> None:
        if self.state == "menu":
            self.renderer.draw_menu(difficulty=self.difficulty,
                                    player_first=self.player_first,
                                    flipped=self.flipped)
            return

        move_number = len(self.gs._history) // 2 + 1
        self.renderer.draw_game(
            self.gs,
            selected=self.input.selected,
            target_squares=self.input.target_squares(),
            last_move=self._last_move,
            human_color=self.human_color,
            ai_thinking=self._ai_thinking,
            tick_ms=tick,
            capture_flash=self._capture_flash,
            anim=self._anim,
            difficulty=self.difficulty,
            mode_ava=self.mode_ava,
            muted=self.audio.muted,
            move_number=move_number,
        )
        if self.state == "over":
            self.renderer.draw_game_over(self.gs, human_color=self.human_color,
                                         mode_ava=self.mode_ava)
