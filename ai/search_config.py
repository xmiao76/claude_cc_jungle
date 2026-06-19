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


def baseline_config() -> SearchConfig:
    """Return a configuration with every enhancement disabled.

    This reproduces the original (pre-enhancement) engine behavior, so the
    strength harness can run a fair A/B against :func:`strong_config`.
    """
    bool_overrides = {
        f.name: False for f in fields(SearchConfig) if isinstance(f.default, bool)
    }
    return replace(SearchConfig(), **bool_overrides)
