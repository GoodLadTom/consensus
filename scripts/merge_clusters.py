"""Fold assignment-agent mappings into the taxonomy to produce clusters.json.

Also reports the health signals that matter before the analysis runs: claims
nobody placed, invalid cluster ids, and any position that has swallowed so
much of the corpus that it is a topic rather than a position.
"""
import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--claims", required=True)
    ap.add_argument("--taxonomy", required=True)
    ap.add_argument("--batch-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pattern", default="assigned*.json")
    ap.add_argument("--max-unassigned", type=float, default=3.0,
                    help="percent of claims that may go unplaced before this "
                         "is treated as a taxonomy gap")
    a = ap.parse_args()

    claims = {c["id"]: c for c in json.load(open(a.claims))["claims"]}
    tax = json.load(open(a.taxonomy))["clusters"]
    tax_ids = {c["id"] for c in tax}

    mapping = {}
    for fp in sorted(glob.glob(os.path.join(a.batch_dir, a.pattern))):
        try:
            mapping.update(json.load(open(fp)))
        except (OSError, json.JSONDecodeError) as e:
            print(f"MALFORMED {os.path.basename(fp)}: {str(e)[:60]}")

    missing = [cid for cid in claims if cid not in mapping]
    stray = [cid for cid in mapping if cid not in claims]
    invalid = {k: v for k, v in mapping.items()
               if v not in tax_ids and v != "unassigned"}
    unassigned = [k for k, v in mapping.items() if v == "unassigned"]

    members = defaultdict(list)
    for cid, clu in mapping.items():
        if clu in tax_ids and cid in claims:
            members[clu].append(cid)

    out = []
    for c in tax:
        ids = members.get(c["id"], [])
        if not ids:
            continue
        out.append({"id": c["id"], "label": c["label"],
                    "description": c.get("description", ""),
                    "contradicts": c.get("contradicts", []),
                    "claim_ids": ids})
    json.dump({"clusters": out}, open(a.out, "w"), indent=2)

    placed = sum(len(c["claim_ids"]) for c in out)
    pct = 100 * len(unassigned) / max(len(claims), 1)
    print(f"claims {len(claims)} | mapped {len(mapping)} | placed {placed}")
    print(f"positions with members: {len(out)} of {len(tax)}")
    print(f"unassigned: {len(unassigned)} ({pct:.1f}%)")

    problems = 0
    if missing:
        problems += 1
        print(f"\nMISSING: {len(missing)} claims no agent mapped: "
              f"{', '.join(missing[:6])}\nRe-run those batches.")
    if invalid:
        problems += 1
        print(f"\nINVALID: {len(invalid)} claims sent to a position that does "
              f"not exist: {list(invalid.items())[:4]}")
    if stray:
        print(f"\nnote: {len(stray)} mapped ids are not in the claims file")

    sizes = Counter({c["id"]: len(c["claim_ids"]) for c in out})
    if sizes:
        biggest, n = sizes.most_common(1)[0]
        share = 100 * n / max(placed, 1)
        print(f"\nlargest position: {biggest} with {n} claims ({share:.1f}%)")
        if share > 20:
            problems += 1
            print("  over a fifth of the corpus — that is a topic that has "
                  "swallowed several positions. Split it.")
        print(f"singletons: {sum(1 for c in out if len(c['claim_ids']) == 1)}")

    if pct > a.max_unassigned:
        problems += 1
        print(f"\nunassigned above {a.max_unassigned}% — read them, they name "
              f"the gaps in the taxonomy:")
        for cid in unassigned[:10]:
            print(f"  {claims[cid]['text'][:90]}")

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
