"""Fetch metadata and transcripts for candidate videos.

YouTube rate-limits the caption endpoint per IP, and the budget is cumulative
over a window rather than being purely about concurrency. Measured on
2026-09-08: fetching five at a time returned HTTP 429 on roughly a fifth of
requests immediately, while throttled sequential fetching ran clean for about
35 videos before the same limit began to bite.

So this runs sequentially with a request delay, takes a longer breather every
`--pause-every` videos to stay inside the window, retries whatever still
failed after a cooldown, and reports what it could not get rather than
pretending the corpus is complete. On a 40-video run built this way, 38
arrived and 2 were lost to a limit that would not clear.

Everything is cached by video id. A second run on a related topic re-uses
whatever it already has.
"""
import argparse
import json
import os
import random
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vtt  # noqa: E402


# Everything the rest of the pipeline reads from a video's metadata. yt-dlp
# writes about 2.8MB per video, almost all of it caption URLs for every
# language on the platform and format variants we never look at. The cache is
# meant to persist across runs, so it is slimmed on the way in.
KEEP = ("id", "title", "channel", "channel_id", "channel_follower_count",
        "uploader", "upload_date", "timestamp", "duration", "view_count",
        "like_count", "comment_count", "categories", "tags")


def slim(meta_path):
    """Rewrite an info.json down to the fields we actually use."""
    try:
        with open(meta_path, encoding="utf-8") as fh:
            full = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return
    if len(full) <= len(KEEP) + 2:
        return  # already slimmed
    lean = {k: full.get(k) for k in KEEP if k in full}
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(lean, fh)


def fetch_one(vid, cache_dir, sleep_requests):
    """Return (status, payload). Status is ok | no_captions | rate_limited | error."""
    meta_path = os.path.join(cache_dir, f"{vid}.info.json")
    text_path = os.path.join(cache_dir, f"{vid}.txt")
    none_path = os.path.join(cache_dir, f"{vid}.nocaptions")

    if os.path.exists(meta_path) and os.path.exists(text_path):
        return "cached", None
    # Remember the misses too, or every later run pays for them again.
    if os.path.exists(none_path):
        return "no_captions", None

    proc = subprocess.run([
        "yt-dlp", f"https://www.youtube.com/watch?v={vid}",
        "--skip-download",
        "--write-auto-subs", "--sub-langs", "en", "--sub-format", "vtt",
        "--write-info-json",
        "--sleep-requests", str(sleep_requests),
        "--retries", "3", "--retry-sleep", "exp=5:60",
        "--no-warnings",
        "-o", os.path.join(cache_dir, "%(id)s"),
    ], capture_output=True, text=True)

    err = proc.stderr or ""
    if "429" in err or "Too Many Requests" in err:
        return "rate_limited", err.strip().splitlines()[-1:] or ["429"]

    # yt-dlp names auto-caption files .en.vtt, and sometimes also .en-orig.vtt
    vtt_path = os.path.join(cache_dir, f"{vid}.en.vtt")
    if not os.path.exists(vtt_path):
        alt = os.path.join(cache_dir, f"{vid}.en-orig.vtt")
        vtt_path = alt if os.path.exists(alt) else None

    if not os.path.exists(meta_path):
        return "error", err.strip().splitlines()[-1:] or ["no metadata"]
    slim(meta_path)
    if not vtt_path:
        open(none_path, "w").close()
        return "no_captions", None

    segments = vtt.parse(vtt_path)
    if len(segments) < 20:
        open(none_path, "w").close()
        os.remove(vtt_path)
        return "no_captions", None

    with open(text_path, "w", encoding="utf-8") as fh:
        fh.write(vtt.to_text(segments))
    os.remove(vtt_path)
    for stray in (f"{vid}.en-orig.vtt",):
        p = os.path.join(cache_dir, stray)
        if os.path.exists(p):
            os.remove(p)
    return "ok", None


def load_meta(vid, cache_dir):
    with open(os.path.join(cache_dir, f"{vid}.info.json"), encoding="utf-8") as fh:
        m = json.load(fh)
    return {
        "id": vid,
        "title": m.get("title"),
        "channel": m.get("channel"),
        "channel_subs": m.get("channel_follower_count"),
        "upload_date": m.get("upload_date"),
        "timestamp": m.get("timestamp"),
        "duration": m.get("duration"),
        "view_count": m.get("view_count"),
        "like_count": m.get("like_count"),
        "url": f"https://www.youtube.com/watch?v={vid}",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sleep-requests", type=float, default=1.5)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--target-read", type=int, default=0,
                    help="keep working down the candidate list until this many "
                         "transcripts are in hand, rather than attempting a "
                         "fixed number and landing short")
    ap.add_argument("--pause-every", type=int, default=25,
                    help="videos between longer breathers (0 disables)")
    ap.add_argument("--pause-seconds", type=float, default=45.0)
    a = ap.parse_args()

    os.makedirs(a.cache, exist_ok=True)
    cands = json.load(open(a.candidates))["candidates"]
    if a.limit:
        cands = cands[:a.limit]

    got, dropped, retry_queue = [], [], []

    fetched_this_stretch = 0
    for i, c in enumerate(cands, 1):
        # Stop as soon as we have what we came for. Candidates are ranked, so
        # the ones past this point are the weakest anyway.
        if a.target_read and len(got) >= a.target_read:
            print(f"reached {a.target_read} transcripts after {i - 1} attempts",
                  file=sys.stderr)
            break
        vid = c["id"]
        # Spend the request budget in stretches. Waiting 45s once is cheaper
        # than losing videos to a limit that then takes minutes to clear.
        if (a.pause_every and fetched_this_stretch >= a.pause_every
                and i < len(cands)):
            print(f"pausing {a.pause_seconds:.0f}s to stay inside the rate "
                  f"limit ({i - 1}/{len(cands)} done)", file=sys.stderr)
            time.sleep(a.pause_seconds)
            fetched_this_stretch = 0

        status, detail = fetch_one(vid, a.cache, a.sleep_requests)
        if status == "ok":
            fetched_this_stretch += 1
        if status in ("ok", "cached"):
            got.append(vid)
        elif status == "rate_limited":
            retry_queue.append(vid)
        else:
            dropped.append({"id": vid, "reason": status, "detail": detail})
        print(f"[{i}/{len(cands)}] {vid} {status}", file=sys.stderr)

    # One patient second pass. A 429 is a cooldown, not a verdict.
    if retry_queue:
        print(f"cooling down before retrying {len(retry_queue)} rate-limited",
              file=sys.stderr)
        time.sleep(60)
        for vid in retry_queue:
            time.sleep(random.uniform(3, 6))
            status, detail = fetch_one(vid, a.cache, a.sleep_requests + 2)
            if status in ("ok", "cached"):
                got.append(vid)
            else:
                dropped.append({"id": vid, "reason": status, "detail": detail})
            print(f"[retry] {vid} {status}", file=sys.stderr)

    corpus = []
    by_id = {c["id"]: c for c in cands}
    for vid in got:
        try:
            meta = load_meta(vid, a.cache)
        except (OSError, json.JSONDecodeError):
            dropped.append({"id": vid, "reason": "bad_metadata"})
            continue
        meta["buckets"] = by_id.get(vid, {}).get("buckets", [])
        # Absolute, because extraction agents are handed these paths from a
        # run directory and a relative one resolves against the wrong root.
        meta["transcript"] = os.path.abspath(
            os.path.join(a.cache, f"{vid}.txt"))
        corpus.append(meta)

    dated = [c for c in corpus if c.get("upload_date")]
    print(f"\ncorpus={len(corpus)} dropped={len(dropped)} "
          f"dated={len(dated)}", file=sys.stderr)

    if a.target_read and len(corpus) < a.target_read:
        print(f"\nSHORT: wanted {a.target_read} transcripts, got {len(corpus)}. "
              f"Candidate list exhausted. Widen the queries in phase 0 and "
              f"re-run - the cache keeps everything already fetched.",
              file=sys.stderr)

    json.dump({"corpus": corpus, "dropped": dropped},
              open(a.out, "w"), indent=2)


if __name__ == "__main__":
    main()
