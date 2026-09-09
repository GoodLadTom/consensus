# Changelog

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
