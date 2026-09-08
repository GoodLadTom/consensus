"""Build the candidate video pool for a topic.

Two buckets, deliberately:

  top     plain relevance search - the canonical, most-watched videos on the
          topic, whatever their age.
  recent  the same queries constrained to the last year - what people are
          saying now.

The overlap between them is smaller than you would expect, and the gap is the
whole point. You cannot notice that advice has died if you only ever looked at
current videos.
"""
import argparse
import json
import subprocess
import sys
import urllib.parse

# YouTube's own upload-date search filters. Verified against live results
# rather than taken on trust - these are undocumented and do drift.
SP_THIS_YEAR = "EgIIBQ%253D%253D"
SP_THIS_MONTH = "EgIIBA%253D%253D"


def _run(args):
    p = subprocess.run(args, capture_output=True, text=True)
    return [json.loads(l) for l in p.stdout.splitlines() if l.startswith("{")]


def search(query, limit, sp=None):
    """Flat search - metadata only, no per-video request. Fast and cheap."""
    if sp:
        url = ("https://www.youtube.com/results?search_query="
               + urllib.parse.quote_plus(query) + "&sp=" + sp)
    else:
        url = f"ytsearch{limit}:{query}"
    rows = _run(["yt-dlp", url, "--flat-playlist", "--dump-json",
                 "--playlist-end", str(limit), "--no-warnings"])
    return rows[:limit]


def usable(row, min_seconds, max_seconds):
    """Cheap pre-filter, before we spend a request on anything."""
    dur = row.get("duration")
    if dur is None or dur < min_seconds or dur > max_seconds:
        return False
    if not row.get("id"):
        return False
    return True


def collect(queries, per_query, min_seconds, max_seconds):
    pool = {}
    for q in queries:
        for bucket, sp in (("top", None), ("recent", SP_THIS_YEAR)):
            for row in search(q, per_query, sp):
                vid = row.get("id")
                if not vid or not usable(row, min_seconds, max_seconds):
                    continue
                if vid in pool:
                    # Found by both buckets: worth knowing, it means a video is
                    # both recent and top-ranking.
                    pool[vid]["buckets"] = sorted(
                        set(pool[vid]["buckets"] + [bucket]))
                    pool[vid]["found_by"].append(q)
                    continue
                pool[vid] = {
                    "id": vid,
                    "title": row.get("title"),
                    "channel": row.get("channel") or row.get("uploader"),
                    "duration": row.get("duration"),
                    "view_count": row.get("view_count"),
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "buckets": [bucket],
                    "found_by": [q],
                }
    return pool


def rank(pool, target):
    """Prefer videos several queries agreed on, then reach.

    Appearing under multiple distinct queries is a better relevance signal
    than raw views, which mostly measures channel size.
    """
    rows = list(pool.values())
    for r in rows:
        r["query_hits"] = len(set(r["found_by"]))
    rows.sort(key=lambda r: (r["query_hits"], r.get("view_count") or 0),
              reverse=True)
    return rows[:target]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", required=True,
                    help="JSON list of search queries, or a path to one")
    ap.add_argument("--target", type=int, default=100)
    ap.add_argument("--per-query", type=int, default=12)
    ap.add_argument("--min-seconds", type=int, default=120,
                    help="below this it is a Short or a teaser, not advice")
    ap.add_argument("--max-seconds", type=int, default=7200)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    raw = a.queries
    try:
        queries = json.loads(raw)
    except json.JSONDecodeError:
        queries = json.load(open(raw))

    pool = collect(queries, a.per_query, a.min_seconds, a.max_seconds)
    chosen = rank(pool, a.target)

    both = sum(1 for r in chosen if len(r["buckets"]) > 1)
    recent_only = sum(1 for r in chosen if r["buckets"] == ["recent"])
    print(f"queries={len(queries)} pool={len(pool)} chosen={len(chosen)} "
          f"(recent-only={recent_only} in-both={both})", file=sys.stderr)

    json.dump({"queries": queries, "candidates": chosen},
              open(a.out, "w"), indent=2)


if __name__ == "__main__":
    main()
