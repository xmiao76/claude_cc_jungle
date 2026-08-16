"""Game orchestrator: wires engine, AI, GUI, and input together."""

from __future__ import annotations

import threading
import traceback
from enum import Enum, auto

import pygame

import config
from ai.native import AIEngine, make_ai_player
from config import (
    AI_TIME_HARD_MS,
    DIFFICULTY_LABELS,
    DIFFICULTY_SUBTEXT,
    FPS,
    VERSION,
)
from engine.board import Move
from engine.game_state import GameState
from engine.pieces import Color, piece_id_animal, piece_id_color
from gui.audio import Audio
from gui.input_handler import InputHandler
from gui.renderer import Renderer


class AppState(Enum):
    MENU = auto()
    HUMAN_TURN = auto()
    AI_THINKING = auto()
    AI_VS_AI_THINKING = auto()
    GAME_OVER = auto()


class Controller:
    """Main game loop and state machine."""

    def __init__(self, surface: pygame.Surface) -> None:
        self.surface = surface
        self.renderer = Renderer(surface)
        self.renderer.load_assets()
        self.input_handler = InputHandler()
        self.audio = Audio()

        self.state = AppState.MENU
        self.gs = GameState()
        self.difficulty = 1
        self.mode_ava = False

        self._ai_blue: AIEngine | None = None
        self._ai_black: AIEngine | None = None
        # Monotonic token identifying the current search. A result arriving with a
        # stale token belongs to a position we have already left and is discarded.
        self._ai_generation = 0

        self._hover_hva = False
        self._hover_ava = False
        self._hover_diff = False
        self._hover_first = False
        self._hover_flip = False

        self._hover_replay = False
        self._hover_quit = False
        self._replay_rect: pygame.Rect | None = None
        self._quit_rect: pygame.Rect | None = None

        self._menu_hva_rect: pygame.Rect | None = None
        self._menu_ava_rect: pygame.Rect | None = None
        self._menu_diff_rect: pygame.Rect | None = None
        self._menu_first_rect: pygame.Rect | None = None
        self._menu_flip_rect: pygame.Rect | None = None

        self._human_color = Color.BLUE
        # Settings (reset each launch)
        self.player_first: bool = True
        self.flipped: bool = False
        # When True, the controller will start the AI thread once the current
        # piece animation finishes. Lets the human see their move slide.
        self._pending_ai_after_anim = False

        self._quit_requested = False

        self._clock = pygame.time.Clock()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        while True:
            tick_ms = pygame.time.get_ticks()
            if not self._handle_events(tick_ms):
                break
            if self._quit_requested:
                break
            self._update(tick_ms)
            self._render(tick_ms)
            self._clock.tick(FPS)
        # Stop any search still burning CPU so the process can exit promptly.
        self._abandon_ai_search()

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def _handle_events(self, tick_ms: int) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._go_to_menu()
                elif event.key == pygame.K_u:
                    self._try_undo()
                elif event.key == pygame.K_m:
                    self.audio.toggle_mute()
                elif event.key == pygame.K_f:
                    self._toggle_flip()

            if event.type == config.AI_MOVE_EVENT_TYPE:
                self._on_ai_move(event.move, tick_ms,
                                 getattr(event, "generation", self._ai_generation))

            if event.type == pygame.MOUSEMOTION:
                self._handle_hover(event.pos)

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos, tick_ms)

        return True

    def _handle_hover(self, pos: tuple[int, int]) -> None:
        mx, my = pos
        if self.state == AppState.MENU:
            self._hover_hva = bool(self._menu_hva_rect and self._menu_hva_rect.collidepoint(mx, my))
            self._hover_ava = bool(self._menu_ava_rect and self._menu_ava_rect.collidepoint(mx, my))
            self._hover_diff = bool(self._menu_diff_rect and self._menu_diff_rect.collidepoint(mx, my))
            self._hover_first = bool(self._menu_first_rect and self._menu_first_rect.collidepoint(mx, my))
            self._hover_flip = bool(self._menu_flip_rect and self._menu_flip_rect.collidepoint(mx, my))
        elif self.state == AppState.GAME_OVER:
            self._hover_replay = bool(self._replay_rect and self._replay_rect.collidepoint(mx, my))
            self._hover_quit = bool(self._quit_rect and self._quit_rect.collidepoint(mx, my))

    def _handle_click(self, pos: tuple[int, int], tick_ms: int) -> None:
        mx, my = pos

        if self.state == AppState.MENU:
            if self._menu_hva_rect and self._menu_hva_rect.collidepoint(mx, my):
                self._start_game(ava=False)
            elif self._menu_ava_rect and self._menu_ava_rect.collidepoint(mx, my):
                self._start_game(ava=True)
            elif self._menu_diff_rect and self._menu_diff_rect.collidepoint(mx, my):
                self.difficulty = (self.difficulty + 1) % 3
            elif self._menu_first_rect and self._menu_first_rect.collidepoint(mx, my):
                self.player_first = not self.player_first
            elif self._menu_flip_rect and self._menu_flip_rect.collidepoint(mx, my):
                self._toggle_flip()
            return

        if self.state == AppState.GAME_OVER:
            if self._replay_rect and self._replay_rect.collidepoint(mx, my):
                self._start_game(ava=self.mode_ava)
            elif self._quit_rect and self._quit_rect.collidepoint(mx, my):
                # Leave the loop and let main() shut pygame down once. Calling
                # pygame.quit() here raced the daemon AI thread's event post into
                # a torn-down display subsystem.
                self._quit_requested = True
            return

        # In-game: side-panel buttons take priority
        if self.renderer.flip_button_rect and self.renderer.flip_button_rect.collidepoint(mx, my):
            self._toggle_flip()
            return
        if self.renderer.undo_button_rect and self.renderer.undo_button_rect.collidepoint(mx, my):
            self._try_undo()
            return
        if self.renderer.mute_button_rect and self.renderer.mute_button_rect.collidepoint(mx, my):
            self.audio.toggle_mute()
            return

        if self.state == AppState.HUMAN_TURN:
            move = self.input_handler.handle_click(
                mx, my, self.gs, self._human_color, self.flipped
            )
            if move is not None:
                self._apply_player_move(move, tick_ms)

    # ------------------------------------------------------------------
    # Game start
    # ------------------------------------------------------------------

    def _start_game(self, ava: bool) -> None:
        # Stop and disown any search still running for the previous game before
        # replacing the state it was computed against.
        self._abandon_ai_search()

        self.mode_ava = ava
        self.gs.new_game()
        self.input_handler.reset()
        self._pending_ai_after_anim = False
        # Otherwise a piece from the finished game keeps sliding across the new one.
        self.renderer.clear_transient_effects()

        self._ai_blue = make_ai_player(Color.BLUE, self.difficulty)
        self._ai_black = make_ai_player(Color.BLACK, self.difficulty)

        if ava:
            self.state = AppState.AI_VS_AI_THINKING
            self._start_ai_thread(Color.BLUE)
        else:
            # Blue moves first per the rules; player_first decides who controls Blue.
            self._human_color = Color.BLUE if self.player_first else Color.BLACK
            if self.player_first:
                self.state = AppState.HUMAN_TURN
            else:
                self.state = AppState.AI_THINKING
                self._start_ai_thread(Color.BLUE)

    def _toggle_flip(self) -> None:
        self.flipped = not self.flipped
        self.renderer.flipped = self.flipped

    # ------------------------------------------------------------------
    # AI thread
    # ------------------------------------------------------------------

    def _abandon_ai_search(self) -> None:
        """Invalidate any in-flight search and ask it to stop.

        Bumping the generation makes a result that is already on its way back get
        discarded on arrival; `request_stop` frees the CPU instead of letting an
        orphaned thread run to completion.
        """
        self._ai_generation += 1
        for ai in (self._ai_blue, self._ai_black):
            if ai is not None:
                ai.request_stop()

    def _start_ai_thread(self, color: Color) -> None:
        ai = self._ai_blue if color == Color.BLUE else self._ai_black
        gs_copy = self.gs.copy()
        self._ai_generation += 1
        generation = self._ai_generation

        def _run():
            move = None
            try:
                budget = AI_TIME_HARD_MS if self.difficulty == 2 else 1000
                move = ai.get_best_move(gs_copy, time_budget_ms=budget)
            except Exception:
                # Without this the thread dies silently, no event is ever posted,
                # and the game sits in AI_THINKING forever. Under a --windowed
                # build there is no console, so also surface it in the UI.
                traceback.print_exc()
            try:
                pygame.event.post(pygame.event.Event(
                    config.AI_MOVE_EVENT_TYPE,
                    {"move": move, "generation": generation},
                ))
            except pygame.error:
                # Display torn down while we were thinking; nothing to deliver to.
                pass

        t = threading.Thread(target=_run, daemon=True, name=f"ai-{color.name}-{generation}")
        t.start()

    def _on_ai_move(self, move: Move | None, tick_ms: int, generation: int = 0) -> None:
        # Discard a result computed for a position we have since left — the user
        # pressed Escape, restarted, or undid. Applying it would corrupt the
        # board: `make_move` on an empty source square writes piece id 0 into the
        # grid, XORs a bogus Zobrist key and files a phantom piece.
        if generation != self._ai_generation:
            return
        if self.gs.is_terminal():
            return

        if move is None or move not in self.gs.legal_moves():
            # The search failed (traceback already printed) or returned something
            # illegal for this position. Keep playing rather than freezing, but do
            # not stay silent about it.
            print(f"[controller] discarding unusable AI move {move!r}; "
                  f"falling back to a legal move")
            legal = self.gs.legal_moves()
            if not legal:
                self.state = AppState.GAME_OVER
                return
            move = legal[0]

        if move.captured:
            self.renderer.trigger_capture_flash(move.tc, move.tr, tick_ms)
            self.audio.play("capture")
        else:
            self.audio.play("move")

        self._begin_animation_for_move(move, tick_ms)
        self.gs.apply_move(move)
        self.input_handler.reset()

        if self.gs.is_terminal():
            self.audio.play("win")
            self.state = AppState.GAME_OVER
            return

        if self.mode_ava:
            self.state = AppState.AI_VS_AI_THINKING
            self._start_ai_thread(self.gs.turn)
        else:
            if self.gs.turn == self._human_color:
                self.state = AppState.HUMAN_TURN
            else:
                self.state = AppState.AI_THINKING
                self._start_ai_thread(self.gs.turn)

    # ------------------------------------------------------------------
    # Human move
    # ------------------------------------------------------------------

    def _apply_player_move(self, move: Move, tick_ms: int) -> None:
        if move.captured:
            self.renderer.trigger_capture_flash(move.tc, move.tr, tick_ms)
            self.audio.play("capture")
        else:
            self.audio.play("move")

        self._begin_animation_for_move(move, tick_ms)
        self.gs.apply_move(move)
        self.input_handler.reset()

        if self.gs.is_terminal():
            self.audio.play("win")
            self.state = AppState.GAME_OVER
            return

        # Defer AI start until the human's piece finishes sliding
        self.state = AppState.AI_THINKING
        self._pending_ai_after_anim = True

    def _begin_animation_for_move(self, move: Move, tick_ms: int) -> None:
        # Read the mover's pid BEFORE apply_move (caller hasn't applied yet)
        pid = self.gs.board.get(move.fc, move.fr)
        if pid == 0:
            return
        self.renderer.start_move_animation(
            piece_id_animal(pid), piece_id_color(pid),
            move.fc, move.fr, move.tc, move.tr, tick_ms,
        )

    # ------------------------------------------------------------------
    # Undo
    # ------------------------------------------------------------------

    def _try_undo(self) -> None:
        """Pop both AI and human plies so the human is on move again."""
        if self.mode_ava:
            return
        if self.state not in (AppState.HUMAN_TURN, AppState.GAME_OVER):
            return
        # An undo rewrites the position the AI may still be thinking about.
        self._abandon_ai_search()
        # Need at least one full round (human + AI) to undo cleanly when in HUMAN_TURN,
        # or one ply to roll back the game-over screen.
        if not self.gs.history:
            return
        # Pop the AI's response (if any) first
        if self.gs.turn == self._human_color and len(self.gs.history) >= 2:
            self.gs.undo_move()
            self.gs.undo_move()
        else:
            self.gs.undo_move()
            if self.gs.history and self.gs.turn != self._human_color:
                self.gs.undo_move()
        self.input_handler.reset()
        self.state = AppState.HUMAN_TURN
        self._pending_ai_after_anim = False
        self.renderer.clear_transient_effects()

    def _undo_enabled(self) -> bool:
        # Must agree with the guards in `_try_undo`, or the button greys out in
        # situations where the U key still works.
        return (
            not self.mode_ava
            and self.state in (AppState.HUMAN_TURN, AppState.GAME_OVER)
            and bool(self.gs.history)
        )

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def _update(self, tick_ms: int) -> None:
        # Defer AI thread start until the human's piece animation completes.
        if self._pending_ai_after_anim and not self.renderer.has_active_animation(tick_ms):
            self._pending_ai_after_anim = False
            self._start_ai_thread(self.gs.turn)
            return

        if self.state == AppState.HUMAN_TURN and self.gs.turn != self._human_color:
            self.state = AppState.AI_THINKING
            self._start_ai_thread(self.gs.turn)

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _render(self, tick_ms: int) -> None:
        if self.state == AppState.MENU:
            rects = self.renderer.draw_main_menu(
                self.surface,
                self.difficulty,
                self._hover_hva,
                self._hover_ava,
                self._hover_diff,
                DIFFICULTY_LABELS,
                DIFFICULTY_SUBTEXT,
                VERSION,
                player_first=self.player_first,
                flipped=self.flipped,
                hover_first=self._hover_first,
                hover_flip=self._hover_flip,
            )
            (self._menu_hva_rect, self._menu_ava_rect, self._menu_diff_rect,
             self._menu_first_rect, self._menu_flip_rect) = rects
        else:
            ai_thinking = self.state in (AppState.AI_THINKING, AppState.AI_VS_AI_THINKING)
            self.renderer.draw(
                self.gs,
                self.input_handler.selected,
                self.input_handler.legal_targets,
                ai_thinking,
                tick_ms,
                undo_enabled=self._undo_enabled(),
                muted=self.audio.muted,
            )

            if self.state == AppState.GAME_OVER:
                winner = self.gs.get_winner()
                rects = self.renderer.draw_game_over_overlay(
                    self.surface, winner,
                    self._hover_replay, self._hover_quit,
                )
                self._replay_rect, self._quit_rect = rects

        pygame.display.flip()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _go_to_menu(self) -> None:
        self._abandon_ai_search()
        self.state = AppState.MENU
        self.input_handler.reset()
        self.renderer.clear_transient_effects()
        self._pending_ai_after_anim = False
