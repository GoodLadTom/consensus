"""Score clustered claims by age and decide what is settled, current or expired.

The three-way split is the point of the tool, so it is worth being precise
about what each one asserts:

  settled   Backed across both the old and the recent half of the corpus.
            Advice that has survived contact with a changing platform.
  current   Backed by recent videos, effectively absent from older ones, in a
            corpus with enough old videos that we would expect to have seen it
            if it had been around. Something changed.
  expired   The mirror image, and the reason the old videos are gathered at
            all: well backed in older videos, absent from recent ones, where
            the recent corpus is large enough that the silence is meaningful.

"Absent from recent videos" is a claim about something not being there, so it
is tested rather than eyeballed. Under the null hypothesis that a claim is
still made at its old rate, the number of recent videos backing it is roughly
Poisson with mean (old_rate * n_recent). The probability of seeing none of
them is exp(-mean). Only when that probability is low do we say the advice
died; otherwise it is simply too thin to call.

That test is only valid over videos that were actually read. A video that was
fetched but never extracted from is not evidence of absence - it is silence
about silence - so the denominators here count only videos that extraction
covered, and a video yielding no claims counts only when extraction said so
explicitly. Skipping this distinction invents expired advice out of nothing.

Support is counted in distinct channels, not videos. One channel uploading
five videos that say the same thing is one person's opinion, not five.
"""
import argparse
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timezone

DAYS_PER_YEAR = 365.25


def age_years(upload_date, now):
    if not upload_date:
        return None
    try:
        d = datetime.strptime(str(upload_date), "%Y%m%d").replace(
            tzinfo=timezone.utc)
    except ValueError:
        return None
    return max(0.0, (now - d).days / DAYS_PER_YEAR)


def decay(age, half_life_years):
    """Half-life decay. A claim loses half its weight every half_life years."""
    if age is None:
        return 0.5  # undated: present, but never load-bearing
    return 0.5 ** (age / half_life_years)


def classify(n_recent_ch, n_old_ch, corpus_recent, corpus_old,
             min_backing, alpha):
    """Return (label, p_absent) for a cluster's channel counts."""
    total = n_recent_ch + n_old_ch
    if total < min_backing:
        return "thin", None

    if n_recent_ch and n_old_ch:
        return "settled", None

    if n_old_ch and not n_recent_ch:
        # Backed only in old videos. Would we have expected to see it recently?
        if not corpus_old or not corpus_recent:
            return "thin", None
        old_rate = n_old_ch / corpus_old
        expected = old_rate * corpus_recent
        p_absent = math.exp(-expected)
        if p_absent < alpha:
            return "expired", p_absent
        return "fading", p_absent

    if n_recent_ch and not n_old_ch:
        if not corpus_old or not corpus_recent:
            return "thin", None
        recent_rate = n_recent_ch / corpus_recent
        expected = recent_rate * corpus_old
        p_absent = math.exp(-expected)
        if p_absent < alpha:
            return "current", p_absent
        return "emerging", p_absent

    return "thin", None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--claims", required=True)
    ap.add_argument("--clusters", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--half-life", type=float, default=1.5,
                    help="years for a claim's weight to halve")
    ap.add_argument("--recent-months", type=float, default=12.0)
    ap.add_argument("--min-backing", type=int, default=2,
                    help="distinct channels needed before we call anything")
    ap.add_argument("--alpha", type=float, default=0.10,
                    help="how unlikely an absence must be to count as real")
    ap.add_argument("--assume-full-coverage", action="store_true",
                    help="count every fetched video as read, even ones "
                         "extraction never reported on. Off by default: an "
                         "unread video is not evidence that nobody said it.")
    a = ap.parse_args()

    now = datetime.now(timezone.utc)
    recent_cutoff = a.recent_months / 12.0

    corpus = {v["id"]: v for v in json.load(open(a.corpus))["corpus"]}
    for v in corpus.values():
        v["age"] = age_years(v.get("upload_date"), now)
        v["is_recent"] = (v["age"] is not None and v["age"] <= recent_cutoff)

    dated = []
    corpus_recent = corpus_old = 0

    payload = json.load(open(a.claims))
    claims = {c["id"]: c for c in payload["claims"]}
    clusters = json.load(open(a.clusters))["clusters"]

    # Only videos extraction actually looked at can testify to an absence.
    read = {c["video_id"] for c in payload["claims"]}
    read |= {v for v in payload.get("skipped", []) if v in corpus}
    unread = [v for v in corpus if v not in read]
    if unread and not a.assume_full_coverage:
        for vid in unread:
            corpus.pop(vid)

    dated = [v for v in corpus.values() if v["age"] is not None]
    corpus_recent = sum(1 for v in dated if v["is_recent"])
    corpus_old = len(dated) - corpus_recent

    out = []
    for cl in clusters:
        members = [claims[cid] for cid in cl.get("claim_ids", []) if cid in claims]
        vids = {m["video_id"] for m in members if m.get("video_id") in corpus}
        if not vids:
            continue

        by_channel = defaultdict(list)
        for vid in vids:
            v = corpus[vid]
            by_channel[v.get("channel") or vid].append(v)

        recent_ch, old_ch = set(), set()
        weight = 0.0
        for ch, videos in by_channel.items():
            # A channel counts once, at the weight of its most recent video.
            best = min(videos, key=lambda v: v["age"] if v["age"] is not None else 99)
            weight += decay(best["age"], a.half_life)
            if best["is_recent"]:
                recent_ch.add(ch)
            elif best["age"] is not None:
                old_ch.add(ch)

        label, p_absent = classify(len(recent_ch), len(old_ch),
                                   corpus_recent, corpus_old,
                                   a.min_backing, a.alpha)

        ages = [corpus[v]["age"] for v in vids if corpus[v]["age"] is not None]
        out.append({
            **{k: cl[k] for k in ("id", "label", "description") if k in cl},
            "contradicts": cl.get("contradicts") or [],
            "status": label,
            "p_absent": round(p_absent, 4) if p_absent is not None else None,
            "channels": len(by_channel),
            "channels_recent": len(recent_ch),
            "channels_old": len(old_ch),
            "videos": len(vids),
            "weighted_support": round(weight, 3),
            "newest_years": round(min(ages), 2) if ages else None,
            "oldest_years": round(max(ages), 2) if ages else None,
            "video_ids": sorted(vids),
            "evidence": [
                {"video_id": m["video_id"], "quote": m.get("quote"),
                 "t": m.get("t"), "text": m.get("text"),
                 "upload_date": corpus[m["video_id"]].get("upload_date")}
                for m in members if m.get("video_id") in corpus
            ],
        })

    order = {"settled": 0, "expired": 1, "current": 2, "emerging": 3,
             "fading": 4, "thin": 5}
    out.sort(key=lambda c: (order.get(c["status"], 9), -c["weighted_support"]))

    known = {c["id"] for c in out}
    pairs = set()
    for c in out:
        c["contradicts"] = [x for x in c["contradicts"] if x in known]
        for other in c["contradicts"]:
            pairs.add(tuple(sorted((c["id"], other))))

    counts = defaultdict(int)
    for c in out:
        counts[c["status"]] += 1
    summary = {
        "generated": now.isoformat(),
        "corpus_fetched": len(corpus) + len(unread),
        "corpus_unread": len(unread),
        "corpus_total": len(corpus),
        "corpus_dated": len(dated),
        "corpus_recent": corpus_recent,
        "corpus_old": corpus_old,
        "recent_months": a.recent_months,
        "half_life_years": a.half_life,
        "alpha": a.alpha,
        "status_counts": dict(counts),
        "contradiction_pairs": [list(p) for p in sorted(pairs)],
    }
    print(json.dumps(summary, indent=2))
    json.dump({"summary": summary, "clusters": out}, open(a.out, "w"), indent=2)


if __name__ == "__main__":
    main()
