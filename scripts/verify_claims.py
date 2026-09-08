"""Check extracted claims against the transcripts they came from.

The one failure that would discredit the whole report is a quote nobody said.
Extraction is done by language models over noisy auto-captions, so quotes are
verified mechanically rather than trusted.

Matching is deliberately lenient about punctuation, casing and caption
artefacts, and strict about the words themselves.
"""
import argparse
import json
import re
import sys
from collections import Counter

WORD = re.compile(r"[a-z0-9']+")


def norm(s):
    return " ".join(WORD.findall((s or "").lower()))


def contained(quote, haystack):
    """True if the quote's words appear in order, allowing small caption drift."""
    q, h = norm(quote), norm(haystack)
    if not q:
        return False
    if q in h:
        return True
    # Auto-captions drop or double the odd word. Accept a high-overlap window.
    qw = q.split()
    if len(qw) < 4:
        return False
    hw = h.split()
    need = max(3, int(len(qw) * 0.8))
    want = Counter(qw)
    for i in range(0, max(1, len(hw) - len(qw) + 1)):
        window = Counter(hw[i:i + len(qw) + 4])
        hits = sum(min(c, window[w]) for w, c in want.items())
        if hits >= need:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--claims", required=True)
    ap.add_argument("--max-report", type=int, default=15)
    ap.add_argument("--strip", action="store_true",
                    help="write back a claims file with unverifiable quotes removed")
    a = ap.parse_args()

    corpus = {v["id"]: v for v in json.load(open(a.corpus))["corpus"]}
    payload = json.load(open(a.claims))
    claims = payload["claims"]

    transcripts = {}
    for vid, v in corpus.items():
        try:
            transcripts[vid] = open(v["transcript"], encoding="utf-8").read()
        except OSError:
            transcripts[vid] = ""

    problems, seen, good = [], set(), []
    for c in claims:
        cid, vid = c.get("id"), c.get("video_id")
        if not cid or not vid:
            problems.append(("malformed", cid, "missing id or video_id"))
            continue
        if cid in seen:
            problems.append(("duplicate id", cid, ""))
            continue
        seen.add(cid)
        if vid not in corpus:
            problems.append(("unknown video", cid, vid))
            continue
        if not c.get("quote"):
            problems.append(("no quote", cid, ""))
            continue
        if not contained(c["quote"], transcripts[vid]):
            problems.append(("quote not in transcript", cid, c["quote"][:70]))
            continue
        good.append(c)

    covered = {c["video_id"] for c in good}
    silent = [v for v in corpus if v not in covered]

    per_video = Counter(c["video_id"] for c in good)
    print(f"claims={len(claims)} verified={len(good)} problems={len(problems)}")
    print(f"videos={len(corpus)} with_claims={len(covered)} silent={len(silent)}")
    if per_video:
        print(f"claims per video: min={min(per_video.values())} "
              f"median={sorted(per_video.values())[len(per_video) // 2]} "
              f"max={max(per_video.values())}")

    if problems:
        print("\nproblems:")
        for kind, cid, detail in problems[:a.max_report]:
            print(f"  {kind:26s} {cid} {detail}")
        if len(problems) > a.max_report:
            print(f"  ... and {len(problems) - a.max_report} more")

    if silent:
        print(f"\nno claims extracted from {len(silent)} videos: "
              f"{', '.join(silent[:8])}{' ...' if len(silent) > 8 else ''}")

    if a.strip and problems:
        payload["claims"] = good
        json.dump(payload, open(a.claims, "w"), indent=2)
        print(f"\nstripped to {len(good)} verified claims")

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
