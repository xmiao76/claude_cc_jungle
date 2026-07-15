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

    # --- v1.4 enhancements (not in v13_strong_config) ---
    use_search_repetition: bool = True   # path-cycle / third-visit repetition rule
                                         # (legacy: draw on ANY first recurrence)
    use_fast_movegen: bool = True        # dedicated noisy-move generator +
                                         # non-terminal eval on hot search paths
    use_tt_generation: bool = True       # TT generation aging + O(1) eviction
                                         # (legacy: stale-deep-entry blocking and
                                         # an O(n log n) mid-search eviction sort)
    use_tt_static_eval: bool = True      # reuse static evals cached in the TT
    use_qsearch_tt_move: bool = True     # try the TT best move first in quiescence
    use_stability_time: bool = True      # best-move-stability time management:
                                         # bank unused budget, extend on instability

    # --- Tuning margins (in the same centipawn-like scale as PIECE_VALUES) ---
    rfp_margin: int = 120                 # per ply of depth
    rfp_max_depth: int = 4
    razor_margin: int = 300
    razor_max_depth: int = 2
    futility_margin: int = 150
    futility_max_depth: int = 2
    lmp_base: int = 6                     # base quiet-move count before LMP kicks in


def strong_config() -> SearchConfig:
    """Return the fully-enhanced configuration (all flags on)."""
    return SearchConfig()


# The exact bool flag-set of the v1.3 shipped engine, frozen so the 1.3 engine
# stays reproducible as an A/B regression control after strong_config() gains
# new flags. Any bool flag added after 1.3 is NOT in this set and is therefore
# automatically False in v13_strong_config().
_V13_BOOL_FLAGS = frozenset({
    "use_mvv_lva_fix",
    "use_see_ordering",
    "use_rfp",
    "use_razoring",
    "use_futility",
    "use_lmp",
    "use_partial_iteration",
    "use_smart_time",
    "use_pst",
    "use_den_threat",
    "use_noisy_den_quiescence",
})


def v13_strong_config() -> SearchConfig:
    """Return the shipped v1.3 engine configuration, frozen for regression A/B.

    Every bool flag in :data:`_V13_BOOL_FLAGS` is True, every other bool flag
    (i.e. anything added after 1.3) is False, and tuning margins keep their
    defaults. ``selfplay --a strong --b v13`` measures exactly what the new
    engine gained over the 1.3 release.
    """
    bool_overrides = {
        f.name: (f.name in _V13_BOOL_FLAGS)
        for f in fields(SearchConfig) if isinstance(f.default, bool)
    }
    return replace(SearchConfig(), **bool_overrides)


def baseline_config() -> SearchConfig:
    """Return a configuration with every enhancement disabled.

    This reproduces the original (pre-enhancement) engine behavior, so the
    strength harness can run a fair A/B against :func:`strong_config`.
    """
    bool_overrides = {
        f.name: False for f in fields(SearchConfig) if isinstance(f.default, bool)
    }
    return replace(SearchConfig(), **bool_overrides)
