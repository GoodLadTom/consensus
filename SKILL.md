---
name: consensus
description: Find out what YouTube actually agrees on about a topic, and what it has quietly stopped saying. Searches YouTube for a topic, pulls ~100 transcripts across both the top-ranking and the most recent videos, extracts every specific claim, clusters claims that say the same thing, then weights them by age to separate settled advice from current advice from expired advice. Produces a self-contained HTML report where every position is traceable to a timestamped source. Use when the user types /consensus, or asks what the consensus is on a topic, what most people/creators say about something, whether advice is still current, or wants many videos researched at once instead of one.
---

# consensus

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

## Pipeline

Work through the phase files in order. Each one states its inputs, its output
file, and how to know it worked.

| Phase | File | Who does it |
|---|---|---|
| 0 Scoping | `pipeline/00_scoping.md` | you |
| 1 Discovery | `pipeline/01_discovery.md` | `scripts/discover.py` |
| 2 Fetch | `pipeline/02_fetch.md` | `scripts/fetch.py` |
| 3 Extraction | `pipeline/03_extraction.md` | parallel subagents |
| 4 Clustering | `pipeline/04_clustering.md` | one subagent |
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
4. **Report what was dropped.** Videos without captions, and fetch failures,
   are counted in the report. A corpus of 78 is fine; a corpus of 78 described
   as 100 is not.
5. **Transcripts only.** No comment sections.
6. **What creators say is not what is true.** The report measures agreement,
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
