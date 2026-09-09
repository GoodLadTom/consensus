"""Rough-sort claims into subject domains so taxonomy design can run parallel.

The taxonomy pass is the pipeline's bottleneck because whoever designs the
positions has to see every claim - design from half the pile and you invent
the same position twice. Sharding removes that constraint the only way it can
be removed: split the pile along lines where duplicate positions are unlikely
to arise, so each designer sees everything relevant to its own area.

Routing is deterministic keyword scoring, not a model. It only has to be
roughly right: a claim landing in the neighbouring domain still gets a
sensible position designed for it, and the assignment pass later routes claims
against the merged taxonomy anyway.
"""
import argparse
import json
import os
import re
from collections import Counter

WORD = re.compile(r"[a-z0-9']+")


def score(text, keywords):
    t = " " + " ".join(WORD.findall((text or "").lower())) + " "
    hits = 0
    for k in keywords:
        k = k.strip().lower()
        if not k:
            continue
        # Phrase keywords are worth more than single words: "cold email" is a
        # far stronger signal than "email".
        if f" {k} " in t:
            hits += 2 if " " in k else 1
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--claims", required=True,
                    help="claims.json, or the slim id/text form")
    ap.add_argument("--domains", required=True,
                    help='JSON: {"domains":[{"id":..,"keywords":[..]}]}')
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--min-shard", type=int, default=40,
                    help="fold domains smaller than this into the catch-all")
    ap.add_argument("--show-unrouted", type=int, default=12,
                    help="sample of unrouted claims to print, so the domain "
                         "keywords can be widened where it actually matters")
    a = ap.parse_args()

    os.makedirs(a.out_dir, exist_ok=True)
    raw = json.load(open(a.claims))
    claims = raw["claims"] if isinstance(raw, dict) else raw
    rows = [{"id": c["id"], "t": c.get("text") or c.get("t"),
             "y": c.get("type") or c.get("y")} for c in claims]

    domains = json.load(open(a.domains))["domains"]

    buckets = {d["id"]: [] for d in domains}
    buckets["general"] = []
    for r in rows:
        best, best_score = None, 0
        for d in domains:
            s = score(r["t"], d.get("keywords") or [])
            if s > best_score:
                best, best_score = d["id"], s
        buckets[best or "general"].append(r)

    # A domain too small to be worth an agent goes back in the pot.
    for did in [k for k, v in buckets.items()
                if k != "general" and len(v) < a.min_shard]:
        buckets["general"] += buckets.pop(did)

    written = 0
    for i, (did, rows_) in enumerate(sorted(buckets.items(),
                                            key=lambda kv: -len(kv[1]))):
        if not rows_:
            continue
        path = os.path.join(a.out_dir, f"shard_{did}.json")
        json.dump(rows_, open(path, "w"), indent=1)
        written += 1
        print(f"{did:28s} {len(rows_):5d} claims  -> {os.path.basename(path)}")

    total = sum(len(v) for v in buckets.values())
    gen = len(buckets["general"])
    print(f"\n{written} shards, {total} claims, "
          f"{gen} unrouted ({100 * gen / max(total, 1):.0f}%) in 'general'")
    print(f"largest shard: {max(len(v) for v in buckets.values())} claims "
          f"— that is what the slowest designer reads")
    if gen > total * 0.25:
        print("WARNING: over a quarter unrouted. The domain keywords are too "
              "narrow; widen them or the catch-all becomes the bottleneck "
              "you were trying to remove.")

    if gen and a.show_unrouted:
        import random
        random.seed(0)
        sample = random.sample(buckets["general"],
                               min(a.show_unrouted, gen))
        print(f"\nunrouted sample — widen the domains that should have "
              f"caught these:")
        for r in sample:
            print(f"  {(r['t'] or '')[:96]}")


if __name__ == "__main__":
    main()
