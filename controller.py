"""Game orchestrator: wires engine, AI, GUI, and input together."""

from __future__ import annotations

import threading
from enum import Enum, auto

import pygame

from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE, FPS,
    DIFFICULTY_LABELS, AI_TIME_HARD_MS,
    AI_MOVE_EVENT_TYPE,
)
from engine.game_state import GameState
from engine.pieces import Color
from engine.board import Move
from ai.minimax import AIPlayer
from gui.renderer import Renderer
from gui.input_handler import InputHandler
import config


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

        self.state = AppState.MENU
        self.gs = GameState()
        self.difficulty = 1  # Medium default
        self.mode_ava = False  # AI-vs-AI mode

        # AI players (recreated when game starts)
        self._ai_blue: AIPlayer | None = None
        self._ai_black: AIPlayer | None = None

        # Menu hover state
        self._hover_hva = False
        self._hover_ava = False
        self._hover_diff = False

        # Game-over overlay hover
        self._hover_replay = False
        self._hover_quit = False
        self._replay_rect: pygame.Rect | None = None
        self._quit_rect: pygame.Rect | None = None

        # Menu button rects (set after draw)
        self._menu_hva_rect: pygame.Rect | None = None
        self._menu_ava_rect: pygame.Rect | None = None
        self._menu_diff_rect: pygame.Rect | None = None

        # Human always plays Blue
        self._human_color = Color.BLUE

        self._clock = pygame.time.Clock()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        while True:
            tick_ms = pygame.time.get_ticks()
            if not self._handle_events(tick_ms):
                return
            self._update(tick_ms)
            self._render(tick_ms)
            self._clock.tick(FPS)

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

            if event.type == config.AI_MOVE_EVENT_TYPE:
                self._on_ai_move(event.move, tick_ms)

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
            return

        if self.state == AppState.GAME_OVER:
            if self._replay_rect and self._replay_rect.collidepoint(mx, my):
                self._start_game(ava=self.mode_ava)
            elif self._quit_rect and self._quit_rect.collidepoint(mx, my):
                pygame.quit()
                import sys; sys.exit(0)
            return

        if self.state == AppState.HUMAN_TURN:
            move = self.input_handler.handle_click(mx, my, self.gs, self._human_color)
            if move is not None:
                self._apply_player_move(move, tick_ms)

    # ------------------------------------------------------------------
    # Game start
    # ------------------------------------------------------------------

    def _start_game(self, ava: bool) -> None:
        self.mode_ava = ava
        self.gs.new_game()
        self.input_handler.reset()

        self._ai_blue = AIPlayer(Color.BLUE, self.difficulty)
        self._ai_black = AIPlayer(Color.BLACK, self.difficulty)

        if ava:
            self.state = AppState.AI_VS_AI_THINKING
            self._start_ai_thread(Color.BLUE)
        else:
            self.state = AppState.HUMAN_TURN

    # ------------------------------------------------------------------
    # AI thread
    # ------------------------------------------------------------------

    def _start_ai_thread(self, color: Color) -> None:
        ai = self._ai_blue if color == Color.BLUE else self._ai_black
        gs_copy = self.gs.copy()

        def _run():
            budget = AI_TIME_HARD_MS if self.difficulty == 2 else 1000
            move = ai.get_best_move(gs_copy, time_budget_ms=budget)
            evt = pygame.event.Event(config.AI_MOVE_EVENT_TYPE, {"move": move})
            pygame.event.post(evt)

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def _on_ai_move(self, move: Move | None, tick_ms: int) -> None:
        if move is None or self.gs.is_terminal():
            return

        # Flash capture
        if move.captured:
            self.renderer.trigger_capture_flash(move.tc, move.tr, tick_ms)

        self.gs.apply_move(move)
        self.input_handler.reset()

        if self.gs.is_terminal():
            self.state = AppState.GAME_OVER
            return

        if self.mode_ava:
            # Continue AI-vs-AI
            self.state = AppState.AI_VS_AI_THINKING
            self._start_ai_thread(self.gs.turn)
        else:
            # Human vs AI
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

        self.gs.apply_move(move)
        self.input_handler.reset()

        if self.gs.is_terminal():
            self.state = AppState.GAME_OVER
            return

        # Start AI
        self.state = AppState.AI_THINKING
        self._start_ai_thread(self.gs.turn)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def _update(self, tick_ms: int) -> None:
        # If HUMAN_TURN but it's somehow AI's turn (shouldn't happen), fix it
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
            )
            self._menu_hva_rect, self._menu_ava_rect, self._menu_diff_rect = rects
        else:
            ai_thinking = self.state in (AppState.AI_THINKING, AppState.AI_VS_AI_THINKING)
            self.renderer.draw(
                self.gs,
                self.input_handler.selected,
                self.input_handler.legal_targets,
                ai_thinking,
                tick_ms,
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
        self.state = AppState.MENU
        self.input_handler.reset()
