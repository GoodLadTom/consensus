# Changelog

## 0.2.0 — 2026-09-09

Sharded the taxonomy pass, the pipeline's one serial stage. **Measured 4.0x:
7.6 minutes across 14 designers against 30.3 on one**, with zero cross-domain
duplicate positions and keyword collisions down from 2.8% to 0.3%. A full run
goes from 72 minutes to roughly 50, and fetch time is now the largest cost.

### The instruction sharding does not work without

Fourteen designers left to their own judgement produced **900 positions where
one designer over the same claims produced 220** — four times too fine. A
designer seeing only its own 150 claims splits hairs that do not matter at
corpus scale, because nothing in its view says what detail the corpus can
support. The report only calls a position a consensus when two independent
channels back it, so a taxonomy that fine fragments support and the whole
report reads "not enough evidence". Faster and worse is not a trade worth
making.

Giving each designer an explicit target of `shard_size / 7` cut 210 positions
to 78 across three tested shards, a 2.7x reduction, landing at 4.9 claims per
position. `merge_taxonomy.py` now measures this and says what to re-run with.

### Designers overshoot the target, and should

All three tested designers independently gave the same reason for exceeding
their target: about eleven of their positions existed only as one half of a
disagreement they were forbidden to merge. A domain where creators argue needs
more positions than one where they agree, because every disagreement costs
two. The sharded pass surfaced far more contradictions than the single pass
did. The guidance says not to chase the target exactly — tidiness bought by
merging real disagreements is the one thing this pipeline must never do.

### Added

- `shard_claims.py` — deterministic keyword routing of claims into domains
- `merge_taxonomy.py` — merges per-domain taxonomies, makes contradictions
  symmetric, and reports granularity plus cross-domain near-duplicate labels
- `make_batches.py`, `merge_claims.py`, `merge_clusters.py` — the three stages
  that previously ran on improvised shell, each verified to reproduce the
  first full run's output exactly
- `check_taxonomy.py` — keyword collision and contradiction hygiene, run
  before any claim is routed

### Also

- Report order is settled, expired, current, then contested. What to do and
  what to stop doing come before where the field is still arguing.
- Claim texts do not deduplicate — 1,623 of 1,623 are distinct, because
  extraction agents write them in their own words. Compressing the designer's
  input that way does not work; sharding is the only lever.

## 0.1.0 — 2026-09-09

First public release. One complete run behind it: 105 transcripts, 71
channels, 1,623 claims, 72 minutes, shipped in `examples/lead-generation/`.

### What it does

Reads about a hundred YouTube transcripts on a topic and reports what the
field agrees on, separating advice that has held up from advice that has
quietly died. Every position traces to a timestamped quote; every video is
credited and linked.

### Decisions worth knowing

- **Support is counted in distinct channels, not videos.** One creator
  uploading the same advice five times is one opinion.
- **`expired` and `current` are assertions about absence, so they are tested.**
  Under the null that a position is still made at its old rate, the count of
  recent videos backing it is roughly Poisson; the probability of seeing none
  is `exp(-expected)`. Below the threshold it is called dead, otherwise it is
  filed as `fading` and no claim is made.
- **A corpus that cannot reach 100 videos runs on what exists.** Padding with
  loosely related videos produces a worse consensus than a small honest one.
  The report states the corpus size and the minimum backing a position needed
  before `expired` could fire at all.

### Two bugs the first live run found

- **Coverage.** The absence test divided by every video fetched, including
  ones extraction never read. A video nobody opened is not evidence of
  silence. It now counts only videos extraction covered, and
  `verify_claims.py --require-coverage` exits 2 rather than let a partial
  read through.
- **Sampling.** The recent half of a corpus is partly drawn from a
  date-filtered search that reaches newer, more tactical videos; the older
  half can only come from relevance ranking, which favours evergreen strategy
  videos. On the live run that was 49% against 0%. Compared directly, ordinary
  advice looked dead — the run reported "follow-ups produce most booked
  meetings" as expired. The test now runs only over videos relevance search
  reached, and a single recent backer anywhere blocks an expired verdict.
  Expired went from 10 to 4; the minimum backing rose from 3 channels to 6.

### Measured, not estimated

- YouTube rate-limits captions per IP on a cumulative budget. Parallel
  fetching returns HTTP 429 immediately; throttled sequential fetching lasts
  about 35 videos. The fetcher paces itself and retries.
- Auto-caption VTT carries ~4.4x redundancy, stripped before extraction.
- yt-dlp writes ~2.8MB of metadata per video, almost all of it unused. Slimmed
  by ~3,600x on the way into the cache.
- Video ids can begin with a hyphen, which breaks shell tools.
- 100 transcripts is ~362,000 tokens of source, ~36,000 per agent across ten
  agents. Context is never the constraint; fetch time and the single-agent
  taxonomy pass are.
