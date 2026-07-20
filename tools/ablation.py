"""Parallel ablation: measure several engine configs against the baseline.

Runs many self-play shards across CPU cores (deterministic, node-limited) and
prints an Elo table sorted by score, so it's clear which features help or hurt.

    python -m tools.ablation --games 40 --nodes 6000
"""

from __future__ import annotations

import argparse
import multiprocessing as mp

from tools.strength_harness import elo, parse_config, run_match

DEFAULT_CONFIGS = [
    "enhanced",
    "no:eval_pst",
    "no:nmp",
    "no:lmr",
    "no:see",
    "no:extensions",
    "no:aspiration",
    "no:history",
    "only:pvs,history,see",
    "baseline",          # sanity: should score ~50% vs baseline
]


def _shard(task):
    cfg_spec, shard_idx, games, nodes, seed = task
    res = run_match(parse_config(cfg_spec), parse_config("baseline"),
                    games=games, nodes=nodes, seed=seed + shard_idx * 997)
    return cfg_spec, res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40, help="games per config (total)")
    ap.add_argument("--nodes", type=int, default=6000)
    ap.add_argument("--shards", type=int, default=4)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--configs", nargs="*", default=DEFAULT_CONFIGS)
    args = ap.parse_args()

    per_shard = max(2, args.games // args.shards)
    tasks = [(c, s, per_shard, args.nodes, args.seed)
             for c in args.configs for s in range(args.shards)]
    print(f"{len(args.configs)} configs x {args.shards} shards x {per_shard} games "
          f"@ {args.nodes} nodes  ({len(tasks)} shards, {args.workers} workers)")

    with mp.Pool(args.workers) as pool:
        results = pool.map(_shard, tasks)

    agg: dict[str, dict] = {}
    for cfg, res in results:
        a = agg.setdefault(cfg, {"games": 0, "a_wins": 0, "a_losses": 0, "draws": 0})
        for k in ("games", "a_wins", "a_losses", "draws"):
            a[k] += res[k]

    rows = []
    for cfg, a in agg.items():
        n = a["games"]
        s = (a["a_wins"] + 0.5 * a["draws"]) / n
        rows.append((s, cfg, a))
    rows.sort(reverse=True)

    print()
    print(f"{'config':26s} {'+W':>4} {'-L':>4} {'=D':>4}  {'score':>7}  {'Elo':>7}  games")
    print("-" * 66)
    for s, cfg, a in rows:
        print(f"{cfg:26s} {a['a_wins']:>4} {a['a_losses']:>4} {a['draws']:>4}  "
              f"{s * 100:6.1f}%  {elo(s):+7.0f}  {a['games']}")


if __name__ == "__main__":
    main()
