"""Check a clustering taxonomy before claims are routed through it.

The assignment pass routes on `keywords`, so a keyword appearing on two
positions is not a cosmetic problem: it sends claims to whichever position
happened to list the phrase rather than the one that means it. On the first
live run eight assignment agents independently reported this, every one of
them naming keyword collisions as the reason for a weak placement.

Catch it here, where it is cheap to fix, rather than in the report.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--taxonomy", required=True)
    ap.add_argument("--max-report", type=int, default=20)
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero on collisions, not just report them")
    a = ap.parse_args()

    clusters = json.load(open(a.taxonomy))["clusters"]
    ids = {c["id"] for c in clusters}
    problems = 0

    dupe_ids = [k for k, v in Counter(c["id"] for c in clusters).items() if v > 1]
    if dupe_ids:
        problems += len(dupe_ids)
        print(f"duplicate ids: {dupe_ids}")

    labels = defaultdict(list)
    for c in clusters:
        labels[(c.get("label") or "").strip().lower()].append(c["id"])
    dupe_labels = {k: v for k, v in labels.items() if len(v) > 1}
    if dupe_labels:
        problems += len(dupe_labels)
        print(f"duplicate labels: {len(dupe_labels)}")
        for lab, who in list(dupe_labels.items())[:5]:
            print(f"  {lab[:60]!r}: {who}")

    # Contradiction hygiene
    dangling, asymmetric = [], []
    contra = {c["id"]: set(c.get("contradicts") or []) for c in clusters}
    for cid, others in contra.items():
        for o in others:
            if o not in ids:
                dangling.append((cid, o))
            elif cid not in contra.get(o, set()):
                asymmetric.append((cid, o))
    if dangling:
        problems += len(dangling)
        print(f"\ndangling contradicts: {len(dangling)}")
        for x in dangling[:a.max_report]:
            print(f"  {x[0]} -> {x[1]} (does not exist)")
    if asymmetric:
        problems += len(asymmetric)
        print(f"\none-sided contradicts: {len(asymmetric)}")
        for x in asymmetric[:a.max_report]:
            print(f"  {x[0]} -> {x[1]}, but not back")

    # Keyword collisions: the one that actually misroutes claims.
    owners = defaultdict(list)
    for c in clusters:
        for k in c.get("keywords") or []:
            owners[k.strip().lower()].append(c["id"])
    collisions = {k: v for k, v in owners.items() if len(v) > 1}

    no_kw = [c["id"] for c in clusters if not (c.get("keywords") or [])]
    if no_kw:
        problems += len(no_kw)
        print(f"\npositions with no routing keywords: {len(no_kw)}")
        print("  " + ", ".join(no_kw[:10]))

    # A position whose every keyword is shared cannot be routed to on keywords
    # at all - it will only ever win a claim by an agent's own judgement.
    undistinguished = []
    for c in clusters:
        kws = [k.strip().lower() for k in (c.get("keywords") or [])]
        if kws and all(len(owners[k]) > 1 for k in kws):
            undistinguished.append(c["id"])

    print(f"\npositions: {len(clusters)}")
    print(f"keywords: {len(owners)} distinct, {sum(len(v) for v in owners.values())} total")
    print(f"colliding keywords: {len(collisions)} "
          f"({100 * len(collisions) / max(len(owners), 1):.1f}% of distinct)")
    print(f"positions with no distinctive keyword: {len(undistinguished)}")

    if collisions:
        worst = sorted(collisions.items(), key=lambda kv: -len(kv[1]))
        print(f"\nmost-shared keywords:")
        for k, who in worst[:a.max_report]:
            print(f"  {len(who)}x {k!r}: {', '.join(who[:4])}"
                  + (" ..." if len(who) > 4 else ""))
    if undistinguished:
        print(f"\npositions routable only by judgement:")
        print("  " + ", ".join(undistinguished[:a.max_report])
              + (" ..." if len(undistinguished) > a.max_report else ""))

    problems += len(collisions) + len(undistinguished)
    return 1 if (a.strict and problems) else 0


if __name__ == "__main__":
    sys.exit(main())
