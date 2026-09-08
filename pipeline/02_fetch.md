# Phase 2 — Fetch

**Input:** `$RUN/candidates.json` · **Output:** `$RUN/corpus.json`, `cache/*.txt`

```bash
python3 scripts/fetch.py \
  --candidates "$RUN/candidates.json" \
  --cache cache \
  --target-read 100 \
  --out "$RUN/corpus.json"
```

`--target-read 100` works down the ranked candidate list until 100 transcripts
are actually in hand, then stops. This is the difference between *attempting*
100 and *getting* 100 — attempting exactly 100 lands somewhere in the low
nineties once captions and rate limits take their cut.

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
- **`SHORT:` in the output** — the candidate list ran out before 100
  transcripts were in hand. Try **once** to fix it: go back to Phase 0, add
  three or four genuinely different queries, and re-run. The cache keeps
  everything already fetched, so the second pass only pays for new videos.

  If it is still short after that, the topic simply does not have 100 videos
  on YouTube. **Carry on with what you have.** Do not pad the corpus with
  loosely related videos to hit a number — a consensus assembled from videos
  that are not really about the topic is worse than a small honest one. Say
  the corpus was short, and why, when you report back.
- **`corpus` under 15** — below this the report will label itself as too small
  to call a consensus, which is correct. Still worth running if the topic is
  genuinely niche; just lead with that when you report back.

Transcripts land in `cache/<id>.txt` as clean prose with a `[mm:ss]` marker
every 30 seconds. Rolling-caption duplication is already stripped, which is
about a 4x saving on extraction tokens.
