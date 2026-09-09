"""Combine per-domain taxonomies into one, and report what needs a human eye.

Designers work on separate domains in parallel, so they cannot see each
other's positions. Two of them can still land on the same idea from different
angles — "reply to a cold email" and "reply to a DM" are one position or two
depending on the corpus. This finds the candidates cheaply, by comparing
labels rather than re-reading claims, and leaves the judgement call to the
merge agent.

Also does the mechanical work no agent should waste tokens on: id collision
checks, keyword collisions across domains, and contradiction symmetry.
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

WORD = re.compile(r"[a-z0-9']+")
STOP = {"the", "a", "an", "to", "of", "and", "is", "in", "for", "you", "your",
        "it", "that", "on", "with", "be", "are", "not", "or", "as", "at", "by",
        "from", "this", "than", "rather", "should", "can", "will", "than"}


def shingle(label):
    return {w for w in WORD.findall((label or "").lower()) if w not in STOP}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard-dir", required=True)
    ap.add_argument("--pattern", default="tax_*.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--claims", default=None,
                    help="claims.json, to check the taxonomy's granularity")
    ap.add_argument("--target-density", type=float, default=7.0,
                    help="claims per position the corpus should support. "
                         "Calibrated at ~7 on the first full run.")
    ap.add_argument("--similar", type=float, default=0.6,
                    help="label overlap above which two positions from "
                         "different domains are flagged as possible duplicates")
    a = ap.parse_args()

    clusters, origin = [], {}
    for fp in sorted(glob.glob(os.path.join(a.shard_dir, a.pattern))):
        dom = os.path.basename(fp)[4:-5]
        try:
            d = json.load(open(fp))
        except (OSError, json.JSONDecodeError) as e:
            print(f"MALFORMED {os.path.basename(fp)}: {str(e)[:60]}")
            continue
        got = d.get("clusters", [])
        for c in got:
            origin[c["id"]] = dom
        clusters += got
        print(f"{dom:32s} {len(got):4d} positions")

    dupe_ids = [k for k, v in Counter(c["id"] for c in clusters).items() if v > 1]
    ids = {c["id"] for c in clusters}

    # Contradictions can only be recorded within a domain, so cross-domain
    # references are expected to be absent rather than broken. Drop danglers
    # quietly but make the asymmetric ones symmetric.
    by_id = {c["id"]: c for c in clusters}
    for c in clusters:
        c["contradicts"] = [x for x in (c.get("contradicts") or []) if x in ids]
    for c in clusters:
        for o in c["contradicts"]:
            if c["id"] not in by_id[o].setdefault("contradicts", []):
                by_id[o]["contradicts"].append(c["id"])

    json.dump({"clusters": clusters}, open(a.out, "w"), indent=2)

    print(f"\nmerged: {len(clusters)} positions from "
          f"{len(set(origin.values()))} domains")
    if dupe_ids:
        print(f"DUPLICATE ids across domains: {dupe_ids[:8]} — prefix them")

    # Cross-domain near-duplicates: the only thing that needs judgement.
    sh = {c["id"]: shingle(c.get("label")) for c in clusters}
    pairs = []
    items = list(sh.items())
    for i, (aid, sa) in enumerate(items):
        if not sa:
            continue
        for bid, sb in items[i + 1:]:
            if origin.get(aid) == origin.get(bid) or not sb:
                continue
            j = len(sa & sb) / len(sa | sb)
            if j >= a.similar:
                pairs.append((round(j, 2), aid, bid))
    pairs.sort(reverse=True)

    kw = defaultdict(set)
    for c in clusters:
        for k in c.get("keywords") or []:
            kw[k.strip().lower()].add(c["id"])
    collisions = {k: v for k, v in kw.items() if len(v) > 1}

    # Granularity is the trap in sharded design: a designer seeing only its
    # own 150 claims splits them far finer than one seeing all 1,600, because
    # nothing tells it what level of detail the corpus can actually support.
    if a.claims:
        try:
            n = len(json.load(open(a.claims))["claims"])
        except (OSError, json.JSONDecodeError, KeyError):
            n = 0
        if n and clusters:
            density = n / len(clusters)
            print(f"\ngranularity: {len(clusters)} positions for {n} claims "
                  f"= {density:.1f} claims each (target {a.target_density:.0f})")
            if density < a.target_density * 0.6:
                want = int(n / a.target_density)
                print(f"  TOO FINE. Support fragments across too many "
                      f"positions and most end up below the independent-"
                      f"channel floor, reported as thin. Re-run the designers "
                      f"with an explicit target of roughly {want} positions "
                      f"total, shared out in proportion to shard size.")
            elif density > a.target_density * 1.8:
                print("  TOO COARSE. Positions this broad are topics, and "
                      "they hide the disagreements the report exists to show.")

    print(f"cross-domain near-duplicate labels: {len(pairs)}")
    for j, x, y in pairs[:20]:
        print(f"  {j}  [{origin.get(x)}] {by_id[x]['label'][:52]}")
        print(f"      [{origin.get(y)}] {by_id[y]['label'][:52]}")
    print(f"\nkeyword collisions: {len(collisions)} of {len(kw)} distinct "
          f"({100 * len(collisions) / max(len(kw), 1):.1f}%)")

    if pairs:
        print("\nSend those pairs to one merge agent. Give it the labels and "
              "descriptions only, never the claims — that is what makes the "
              "merge cheap.")
    return 1 if dupe_ids else 0


if __name__ == "__main__":
    sys.exit(main())
