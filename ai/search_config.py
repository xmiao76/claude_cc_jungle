"""Search / evaluation feature configuration for the Jungle AI.

A :class:`SearchConfig` is an immutable bundle of feature toggles and tuning
margins for the negamax search (``ai/minimax.py``) and static evaluation
(``ai/evaluator.py``).

Two canonical configurations:

* :func:`strong_config` — every enhancement enabled (the shipped engine).
* :func:`baseline_config` — every enhancement disabled; reproduces the
  pre-enhancement engine behavior. Used by the strength harness
  (``tools/strength_harness.py``) as the A/B control so each enhancement can be
  measured head-to-head.

Every search/eval enhancement reads ``self.cfg.<flag>`` and falls back to the
original behavior when the flag is ``False``. This makes each change
individually toggleable, revertible, and measurable.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace


@dataclass(frozen=True)
class SearchConfig:
    """Immutable engine feature/tuning configuration."""

    # --- Move ordering (Task 2) ---
    use_mvv_lva_fix: bool = True          # proper victim*K - attacker capture key
    use_see_ordering: bool = True         # demote SEE-losing captures behind quiets

    # --- Shallow-depth pruning (Task 3) ---
    use_rfp: bool = True                  # reverse futility / static null move
    use_razoring: bool = True            # drop to quiescence when far below alpha
    use_futility: bool = True            # skip quiet moves near the frontier
    use_lmp: bool = True                 # late-move (move-count) pruning

    # --- Iterative deepening / time management (Task 4) ---
    use_partial_iteration: bool = True   # keep best move from an interrupted iteration
    use_smart_time: bool = True          # soft limit; don't start unfinishable iterations

    # --- Evaluation (Tasks 5-6) ---
    use_pst: bool = True                 # piece-square tables
    use_den_threat: bool = True          # den-threat / den-safety term
    use_noisy_den_quiescence: bool = True  # consider den-entry moves in quiescence

    # --- Evaluation rebuild: MEASURED AND REJECTED (see V2_FLAGS) ---
    # Each of these was implemented, then played head-to-head against the same
    # engine with the flag off — 40 games, 250ms/move, paired colour-swapped
    # openings. Every one came out *weaker*, so all four default to False. The
    # code and the numbers are kept so the result is not rediscovered the hard way.
    #
    #   use_hanging             -255 Elo  LOS  0.0%  (W5-L30-D5)   decisive
    #   use_real_jump_ready      -98 Elo  LOS  3.1%  (W12-L23-D5)
    #   use_true_den_distance    -70 Elo  LOS  7.2%  (W11-L19-D10)
    #   use_tuned_piece_values   -44 Elo  LOS 18.5%  (W13-L18-D9)
    #   all four together        -53 Elo  LOS 11.2%  over 60 games
    use_tuned_piece_values: bool = False  # Rat-premium values instead of 100x rank
    use_true_den_distance: bool = False   # BFS moves-to-den instead of Manhattan
    use_hanging: bool = False             # penalise attacked & undefended pieces
    use_real_jump_ready: bool = False     # jump-ready checks blockers, not just geometry
    use_real_mobility: bool = False       # mobility respects river/den/capture legality

    # --- Search rebuild: measured individually against this config minus the flag,
    #     40 games, 250ms/move, paired colour-swapped openings ---
    #
    #   use_lmr_guards     +80 Elo  LOS 94.1%  (W21-L12-D7)
    #   use_tt_aging       +80 Elo  LOS 94.1%  (W21-L12-D7)
    #   use_side_history   +53 Elo  LOS 85.6%  (W19-L13-D8)
    #   use_root_ordering   +0 Elo  LOS 50.0%  (W17-L17-D6)  <- exactly neutral, off
    use_side_history: bool = True        # history keyed by side, capped, with malus
    use_lmr_guards: bool = True          # never reduce a PV node or a den-entry move
    use_tt_aging: bool = True            # generation-based TT replacement and eviction
    # Dead even over 40 games. The TT move already supplies most of the root
    # ordering, and re-sorting by last iteration's scores displaces it. Kept off:
    # a neutral result does not justify the extra state and the per-iteration dict.
    use_root_ordering: bool = False      # order root moves by the last iteration's scores

    # --- Tuning margins (in the same centipawn-like scale as PIECE_VALUES) ---
    rfp_margin: int = 120                 # per ply of depth
    rfp_max_depth: int = 4
    razor_margin: int = 300
    razor_max_depth: int = 2
    futility_margin: int = 150
    futility_max_depth: int = 2
    lmp_base: int = 6                     # base quiet-move count before LMP kicks in


# Evaluation terms that were built, measured, and found to lose strength. They
# default off; `experimental_config` turns them on for anyone revisiting them.
V2_FLAGS: tuple[str, ...] = (
    "use_tuned_piece_values",
    "use_true_den_distance",
    "use_hanging",
    "use_real_jump_ready",
    "use_real_mobility",
)

# Search features that measured neutral. Not wrong, just not worth their weight.
NEUTRAL_FLAGS: tuple[str, ...] = (
    "use_root_ordering",
)

# Everything that ships disabled *because a measurement said so*, rather than
# because it is unfinished. Any flag outside this set is on in `strong_config`.
DISABLED_BY_MEASUREMENT: tuple[str, ...] = V2_FLAGS + NEUTRAL_FLAGS


def strong_config() -> SearchConfig:
    """Return the shipped engine: the strongest configuration actually measured.

    Deliberately *not* "every flag on". Four evaluation terms measured weaker than
    their absence (see :class:`SearchConfig`), so switching everything on makes the
    engine worse. Strength is decided by the harness, not by feature count.
    """
    return SearchConfig()


def experimental_config() -> SearchConfig:
    """Return `strong_config` plus the rejected evaluation terms.

    Kept so the terms remain reachable for re-tuning; measured at roughly -53 Elo
    against `strong_config`, so it is not a configuration to ship.
    """
    return replace(SearchConfig(), **{name: True for name in V2_FLAGS})


def baseline_config() -> SearchConfig:
    """Return a configuration with every enhancement disabled.

    This reproduces the original (pre-enhancement) engine behavior, so the
    strength harness can run a fair A/B against :func:`strong_config`.
    """
    bool_overrides = {
        f.name: False for f in fields(SearchConfig) if isinstance(f.default, bool)
    }
    return replace(SearchConfig(), **bool_overrides)


def v1_config() -> SearchConfig:
    """Alias for :func:`strong_config`, kept for the harness's config names.

    The evaluation rebuild's terms are off by default, so "v1" and "strong" now
    describe the same engine.
    """
    return strong_config()


def piece_values(cfg: SearchConfig | None) -> tuple[int, ...]:
    """Return the piece-value table this configuration evaluates with.

    Indexed by rank, index 0 = empty. Evaluation, SEE and quiescence delta
    pruning must all read the *same* table or they will disagree about what a
    capture is worth.

    ``cfg=None`` means the shipped default, which is the linear table: the tuned
    one measured weaker (see :class:`SearchConfig`).
    """
    from config import PIECE_VALUES_LINEAR, PIECE_VALUES_TUNED

    if cfg is not None and cfg.use_tuned_piece_values:
        return PIECE_VALUES_TUNED
    return PIECE_VALUES_LINEAR
