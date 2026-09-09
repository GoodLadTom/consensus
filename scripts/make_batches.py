"""Split a corpus into balanced batches for parallel extraction agents.

Balanced by transcript length rather than video count, so no agent draws all
the long videos and holds up the stage. Paths written out are absolute:
agents work from a run directory and resolve a relative path against the
wrong root.
"""
import argparse
import json
import os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--batches", type=int, default=11)
    a = ap.parse_args()

    os.makedirs(a.out_dir, exist_ok=True)
    corpus = json.load(open(a.corpus))["corpus"]

    for v in corpus:
        try:
            with open(v["transcript"], encoding="utf-8") as fh:
                v["_words"] = len(fh.read().split())
        except OSError:
            v["_words"] = 0

    # Longest first into the lightest batch: a greedy fit that keeps the
    # slowest agent as fast as possible.
    corpus.sort(key=lambda v: -v["_words"])
    batches = [[] for _ in range(a.batches)]
    load = [0] * a.batches
    for v in corpus:
        i = load.index(min(load))
        batches[i].append(v)
        load[i] += v["_words"]

    for i, b in enumerate(batches):
        rows = [{"video_id": v["id"], "title": v.get("title"),
                 "channel": v.get("channel"),
                 "upload_date": v.get("upload_date"),
                 "transcript": os.path.abspath(v["transcript"])} for v in b]
        with open(os.path.join(a.out_dir, f"batch{i:02d}.json"), "w") as fh:
            json.dump(rows, fh, indent=2)
        print(f"batch{i:02d}: {len(b):3d} videos, {load[i]:7,} words")

    print(f"\n{a.batches} batches, {len(corpus)} videos, {sum(load):,} words")
    missing = [v["id"] for v in corpus if not v["_words"]]
    if missing:
        print(f"WARNING: {len(missing)} transcripts unreadable: "
              f"{', '.join(missing[:6])}")


if __name__ == "__main__":
    main()
