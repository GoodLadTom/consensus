# consensus

A Claude Code skill that reads about a hundred YouTube videos on a topic and
tells you what the field agrees on — and what it has quietly stopped saying.

```
/consensus how to grow on youtube
```

Ten minutes later you get a self-contained HTML report where every position is
traceable to a timestamped source.

## The problem it solves

Ask YouTube how to do anything and you get a thousand videos, each confident,
several contradicting each other, and no way to tell which advice the field
actually shares from which is one person's hobby horse.

Worse, you cannot tell which advice is *dead*. On a fast-moving topic the
highest-ranking video is often three years old and describing a platform that
no longer exists. Summarise it alongside last month's videos and you get a
confident average of two incompatible worlds.

## What it does differently

It gathers old videos on purpose.

Most research tools filter for recency and throw the old material away. This
one keeps both halves, because **you cannot notice advice has died if you only
ever looked at current videos**. Every position lands in one of these:

| Status | Means |
|---|---|
| **Settled** | Backed in both older and recent videos. Has survived a changing field. |
| **Expired** | Well backed in older videos, absent from recent ones by more than chance explains. Dead advice. |
| **Current** | Backed recently, absent from older videos. Something changed. |
| **Emerging / Fading** | Leaning one way, not enough backing to separate from chance. No claim made. |
| **Thin** | Too few independent channels to call. |

`Expired` is the one worth having, and it is the one that needs care, because
it asserts that something is *not there*. So it is tested rather than
eyeballed: under the assumption a position is still made at its old rate, the
number of recent videos backing it is roughly Poisson, and the probability of
seeing none of them is `exp(-expected)`. Only when that is unlikely does the
tool call it dead. Otherwise it says `fading` and makes no claim.

Support is counted in **distinct channels, not videos**. One creator uploading
the same advice five times is one opinion.

## Getting started

Needs Python 3.9+, [yt-dlp](https://github.com/yt-dlp/yt-dlp), and Claude Code.
No YouTube API key, no Google Cloud project, no account.

```bash
git clone https://github.com/GoodLadTom/consensus.git
cd consensus
./install.sh
```

Then in Claude Code:

```
/consensus <any topic>
```

## How it works

| Phase | What happens |
|---|---|
| Scoping | Topic becomes 8-12 distinct search queries |
| Discovery | Each query run twice — plain relevance, and constrained to the last year |
| Fetch | Transcripts pulled via yt-dlp, cleaned, cached by video id |
| Extraction | Parallel agents pull claims specific enough to be wrong |
| Clustering | Claims saying the same thing in different words become one position |
| Analysis | Deterministic age weighting and the absence test |
| Report | One self-contained HTML file |

No video is ever downloaded. Only caption tracks, which are text.

## What it will not do

It measures what creators **say**, not what is true. Popular advice and correct
advice are different things, and a consensus of people copying each other is
still one idea wearing forty hats. The report says this on its face.

It will not invent a consensus. A split field is reported as split, a thin
corpus as thin. "Not enough evidence" is a valid finding here.

It reads transcripts only. No comment sections.

## Notes from building it

A few things that were measured rather than assumed, in case they save you the
same afternoon:

- YouTube rate-limits the caption endpoint **per IP, and the budget is
  cumulative** rather than purely about concurrency. Fetching five at a time
  returned HTTP 429 on roughly a fifth of requests straight away. Throttled
  sequential fetching ran clean for about 35 videos and then hit the same wall.
  So parallelism does not help, and neither does patience alone — the fetcher
  takes a 45-second breather every 25 videos to stay inside the window. On a
  live 40-video run that got 38; the 2 it lost are reported, not hidden.
- Auto-caption VTT is written in a rolling style where each cue repeats the
  previous line plus a few words, with per-word timing tags. Left alone that is
  about 4.4x more text than was spoken. Cleaning it is most of the token bill.
- YouTube's undocumented `sp=` search filters do work through yt-dlp, which is
  how the recent bucket is built without an API key. `EgIIBQ%3D%3D` is
  this year, `EgIIBA%3D%3D` this month — verified against live upload dates
  rather than taken on trust, because they drift.

## Licence

MIT.
