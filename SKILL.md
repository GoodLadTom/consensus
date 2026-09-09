---
name: consensus
description: Find out what YouTube actually agrees on about a topic, and what it has quietly stopped saying. Searches YouTube for a topic, pulls ~100 transcripts across both the top-ranking and the most recent videos, extracts every specific claim, clusters claims that say the same thing, then weights them by age to separate settled advice from current advice from expired advice. Produces a self-contained HTML report where every position is traceable to a timestamped source. Use when the user types /consensus, or asks what the consensus is on a topic, what most people/creators say about something, whether advice is still current, or wants many videos researched at once instead of one.
---

# consensus

**v0.2.0**

Give it a topic. It reads about a hundred YouTube videos on that topic and
tells you what the field agrees on — separating advice that has held up from
advice that has quietly died.

The output answers one question: **when you strip out the outliers, what does
YouTube actually agree on about this, and what has it stopped saying?**

## Why the age split is the whole point

Any tool can summarise videos. The reason this one gathers old videos as well
as recent ones is that you cannot notice advice has died if you only ever
looked at current videos. On a topic like YouTube growth, 2022 advice is often
actively wrong — the platform changed underneath it. Reporting a consensus
that averages 2022 and 2026 together produces confident nonsense.

So every position lands in one of these:

| Status | Means |
|---|---|
| **Settled** | Backed in both older and recent videos. Has survived a changing field. |
| **Expired** | Well backed in older videos, absent from recent ones by more than chance explains. Dead advice. |
| **Current** | Backed recently, absent from older videos. Something changed. |
| **Emerging / Fading** | Leaning one way, but not enough backing to separate from chance. No claim made. |
| **Thin** | Too few independent channels to call. |

`expired` and `current` are assertions about *absence*, so they are tested
rather than eyeballed — see `scripts/analyse.py`. Where an absence could
plausibly be chance, the position is filed as `fading` and no claim is made.

## Run it

```
/consensus <topic>
```

Optionally: `/consensus <topic> --videos 60 --recent-months 18`

## The standard: 100 transcripts, actually read

The target is **100 transcripts, every one of them read**. Not 100 attempted,
not 100 fetched and 60 mined. This is enforced rather than trusted:

1. Discovery gathers **140** candidates, because captions and rate limits take
   a cut of any list.
2. Fetch runs with `--target-read 100` and works down the ranked list until
   100 transcripts are in hand, then stops.
3. Extraction covers **every** video in the corpus, and
   `verify_claims.py --require-coverage` **exits 2** if any video was fetched
   but never reported on. Do not proceed past a non-zero exit.

The reason is not tidiness. Phase 5 decides that advice has expired by testing
whether a position's absence from recent videos is more than chance. That test
divides by how many videos were actually read. Silently reading 60 of 100
does not make the answer noisier — it makes it wrong, and wrong in the
direction of inventing dead advice that was never dead.

## What a full run costs, measured

Timings from the first complete run — 105 videos, 71 channels, 1,623 claims:

| Phase | Wall clock | Notes |
|---|---|---|
| Scoping + discovery | 1 min | 270 candidates down to 140 |
| Fetch | 18 min | rate-limit paced, unavoidable |
| Extraction | 14 min | 11 agents in parallel |
| **Taxonomy design** | **8 min** | **14 agents in parallel (was 30 min on one)** |
| Assignment | 10 min | 8 agents in parallel |
| Analysis + report | seconds | deterministic |
| **Total** | **~50 min** | 72 before the taxonomy pass was sharded |

Context is never the constraint — 100 transcripts is about 362,000 tokens of
source, roughly 36,000 per agent across ten agents. Fetch time is now the
largest single cost and cannot be reduced: YouTube rate-limits captions per IP,
and going faster just gets you blocked.

The taxonomy pass used to be the bottleneck at 30 minutes on one agent.
Sharded across 14 it measured 7.6 minutes, a 4.0x speedup, with no
cross-domain duplicate positions. `pipeline/04_clustering.md` has the method,
including the granularity instruction it does not work without.

**When a topic cannot reach 100**, which happens on genuinely niche subjects,
run with what exists rather than padding the corpus with loosely related
videos to hit a number. The report states the corpus size, the channel count,
the age split, and the minimum backing a position needed before `expired`
could fire at all — so a reader can see how much weight the findings carry.
Say the same thing in the chat, first, before any finding.

## Pipeline

Work through the phase files in order. Each one states its inputs, its output
file, and how to know it worked.

| Phase | File | Who does it |
|---|---|---|
| 0 Scoping | `pipeline/00_scoping.md` | you |
| 1 Discovery | `pipeline/01_discovery.md` | `scripts/discover.py` |
| 2 Fetch | `pipeline/02_fetch.md` | `scripts/fetch.py` |
| 3 Extraction | `pipeline/03_extraction.md` | parallel subagents |
| 4 Clustering | `pipeline/04_clustering.md` | one subagent, then parallel subagents |
| 5 Analysis | `pipeline/05_analysis.md` | `scripts/analyse.py` |
| 6 Report | `pipeline/06_report.md` | `scripts/report.py` |

Set up the run directory first:

```bash
RUN="runs/$(date +%Y-%m-%d)-<topic-slug>"
mkdir -p "$RUN"
```

Transcripts cache in `cache/` keyed by video id and are shared across runs, so
a second run on a neighbouring topic re-fetches almost nothing.

## The rules this skill runs on

1. **Never invent a consensus.** If the field is split, the report says split.
   If a position is thin, it is labelled thin. An honest "not enough evidence"
   beats a confident average.
2. **Count channels, not videos.** One creator uploading the same advice five
   times is one opinion.
3. **Every claim carries a quote and a timestamp.** A position nobody can
   check is not a finding.
4. **Report what was dropped, and credit every source.** Videos without
   captions and fetch failures are counted in the report. A corpus of 78 is
   fine; a corpus of 78 described as 100 is not. Every video used is credited
   by title, channel and date, linked so the reader can watch it.
5. **Corpus size goes first, not in a footnote.** A small corpus does not
   invalidate a run, but it changes what the run can claim. Say how big it was
   before saying what it found.
6. **Transcripts only.** No comment sections.
7. **What creators say is not what is true.** The report measures agreement,
   not correctness, and says so.

## Known limits, state them in the summary

- Only videos with captions can be read. Most have auto-captions; some do not.
- Auto-captions mangle names, jargon and numbers. Fine for spotting consensus,
  occasionally ugly in a direct quote.
- YouTube rate-limits the caption endpoint per IP, on a cumulative budget.
  `fetch.py` runs sequentially, pauses 45s every 25 videos, and retries the
  failures once after a cooldown. Roughly 100 videos takes 13-17 minutes.
  Do not "speed it up" with parallelism — that was measured, and it returns
  HTTP 429 on about a fifth of requests. Expect to lose a small number of
  videos anyway on a long run; they are reported in the reports's summary.
- Search reflects YouTube's ranking, which favours big channels. The corpus is
  what YouTube surfaces, not a random sample of the field.
- **The two halves of the corpus are not sampled the same way**, and this is
  the subtlest trap in the whole tool. Discovery fills the recent half partly
  from a date-filtered search that reaches videos relevance ranking never
  returns — newer, smaller, more tactical. The older half can only come from
  relevance ranking, which favours evergreen strategy videos. On the first
  live run that was 49% of the recent half against 0% of the old half, and
  comparing them directly reported ordinary strategy advice as dead. The
  absence test now runs only over videos relevance search reached; every video
  still counts towards support and weighting. Do not pass
  `--no-bucket-control` unless you know both halves were sampled alike.
