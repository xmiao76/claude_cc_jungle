"""Tests for ai/transposition.py."""

from ai.transposition import (
    TT_EXACT,
    TT_LOWER,
    TranspositionTable,
)


def test_put_get_round_trip():
    tt = TranspositionTable()
    tt.put(123, depth=4, score=42, flag=TT_EXACT, best_move=("m",))
    e = tt.get(123)
    assert e is not None
    assert e.depth == 4 and e.score == 42
    assert e.flag == TT_EXACT and e.best_move == ("m",)


def test_depth_prefer_replacement_keeps_deeper():
    """Writing a shallower entry over a deeper one must NOT replace it."""
    tt = TranspositionTable()
    tt.put(1, depth=8, score=100, flag=TT_EXACT, best_move="deep")
    tt.put(1, depth=2, score=999, flag=TT_EXACT, best_move="shallow")
    e = tt.get(1)
    assert e.depth == 8 and e.best_move == "deep"


def test_depth_prefer_replacement_overwrites_equal_or_shallower():
    """Writing an equal-or-deeper entry replaces."""
    tt = TranspositionTable()
    tt.put(1, depth=3, score=100, flag=TT_EXACT, best_move="old")
    tt.put(1, depth=3, score=200, flag=TT_LOWER, best_move="new")
    e = tt.get(1)
    assert e.score == 200 and e.best_move == "new"


def test_eviction_when_full_keeps_deeper_entries():
    """When full, eviction prefers low-depth entries (keep deeper)."""
    tt = TranspositionTable(max_entries=10)
    # Insert 10 shallow entries
    for k in range(10):
        tt.put(k, depth=1, score=k, flag=TT_EXACT, best_move=k)
    # Insert one deep entry — triggers eviction
    tt.put(999, depth=8, score=42, flag=TT_EXACT, best_move="deep")
    deep = tt.get(999)
    assert deep is not None and deep.depth == 8
    # Table should not exceed bound after eviction + insert
    assert len(tt._table) <= 10
