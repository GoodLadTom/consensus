# Phase 2 — Fetch

**Input:** `$RUN/candidates.json` · **Output:** `$RUN/corpus.json`, `cache/*.txt`

```bash
python3 scripts/fetch.py \
  --candidates "$RUN/candidates.json" \
  --cache cache \
  --out "$RUN/corpus.json"
```

Roughly 13-17 minutes for 100 videos, including the pauses. Tell the user the
number before starting so the wait is expected, then let it run.

**Do not add parallelism, and do not remove the pauses.** Both were measured:
parallel fetching returns HTTP 429 on about a fifth of requests immediately,
and even throttled sequential fetching hits the same limit after roughly 35
videos. The script pauses 45s every 25 videos to stay inside the window and
retries whatever still failed after a cooldown. Losing a couple of videos on a
long run is normal.

## Check before moving on

The script prints `corpus=N dropped=N dated=N`.

- **`dropped` above ~20%** — unusual. Look at the reasons in
  `corpus.json.dropped`. A run of `rate_limited` means the IP is still cooling
  off; wait and re-run, the cache keeps everything already fetched.
- **`dated` well below `corpus`** — the age analysis weakens. Say so later.
- **`corpus` under 30** — too thin for a consensus. Go back to Phase 0 and
  widen, rather than reporting a consensus of twelve videos.

Transcripts land in `cache/<id>.txt` as clean prose with a `[mm:ss]` marker
every 30 seconds. Rolling-caption duplication is already stripped, which is
about a 4x saving on extraction tokens.
