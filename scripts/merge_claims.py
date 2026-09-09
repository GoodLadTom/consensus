"""Merge extraction agent outputs into one claims file.

Refuses to silently lose a video: anything in the corpus that no agent
reported on is named, because Phase 5 divides by how many videos were read.
"""
import argparse
import glob
import json
import os
import sys
from collections import Counter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-dir", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pattern", default="out*.json")
    a = ap.parse_args()

    claims, skipped, bad = [], [], []
    files = sorted(glob.glob(os.path.join(a.batch_dir, a.pattern)))
    for fp in files:
        try:
            d = json.load(open(fp))
        except (OSError, json.JSONDecodeError) as e:
            bad.append((os.path.basename(fp), str(e)[:60]))
            continue
        claims += d.get("claims", [])
        skipped += d.get("skipped", [])
        print(f"{os.path.basename(fp)}: {len(d.get('claims', [])):4d} claims, "
              f"{len(d.get('skipped', []))} skipped")

    for name, err in bad:
        print(f"MALFORMED {name}: {err}")

    dupes = [k for k, v in Counter(c.get("id") for c in claims).items() if v > 1]
    corpus = {v["id"] for v in json.load(open(a.corpus))["corpus"]}
    covered = {c.get("video_id") for c in claims} | set(skipped)
    unaccounted = sorted(corpus - covered)

    json.dump({"claims": claims, "skipped": sorted(set(skipped))},
              open(a.out, "w"), indent=2)

    print(f"\nmerged {len(claims)} claims from {len(files)} batches, "
          f"{len(set(skipped))} skipped, "
          f"{len({c.get('video_id') for c in claims})} videos with claims")
    if dupes:
        print(f"DUPLICATE claim ids: {len(dupes)} — {', '.join(dupes[:5])}")
    if unaccounted:
        print(f"UNACCOUNTED: {len(unaccounted)} corpus videos no agent "
              f"reported on: {', '.join(unaccounted[:8])}")
        print("Re-run those batches. Do not continue.")
    return 1 if (bad or dupes or unaccounted) else 0


if __name__ == "__main__":
    sys.exit(main())
