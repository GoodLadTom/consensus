# Phase 6 — Report

**Input:** `$RUN/analysis.json`, `$RUN/corpus.json` · **Output:** `$RUN/report.html`

```bash
python3 scripts/report.py \
  --analysis "$RUN/analysis.json" \
  --corpus "$RUN/corpus.json" \
  --topic "<the user's topic>" \
  --out "$RUN/report.html"
```

One self-contained file. No network, no CDN, opens anywhere.

The report opens with a corpus-strength banner stating how many videos and
channels it rests on, and the minimum backing a position needed before
`expired` could fire at all. That last number matters: without it, "no expired
advice" reads as "none exists" when it often means "none was detectable".
Both are generated from the analysis — do not hand-write either.

It closes with **Sources**: every video credited by title, channel, date and
view count, with the title linking to the video and each quote linking to the
exact second. Anything fetched but never read is marked `not read` rather than
being passed off as silence.

## Then tell the user, in the chat

Print the findings — do not just hand over a file path. Give them:

1. **The corpus, first, in one line.** How many videos from how many channels,
   and the age split. If the run came up short of 100, say so and say why —
   a niche topic, captions missing, rate limits. Never present a 30-video run
   as though it carried the same weight as a 100-video one.
2. **The headline consensus** — the three or four strongest settled positions,
   in plain language, with how many channels back each.
3. **Anything expired** — stated as "creators used to say X; none of the N
   recent videos do". This is the part they cannot get anywhere else, so lead
   with it if it is interesting.
4. **The real disagreements** — where credible people contradict each other,
   stated as a disagreement rather than averaged away.
5. **What the corpus could not tell you** — videos dropped, whether the old
   half was big enough to make the absence test meaningful, and any query that
   returned thin results. If nothing came out expired, say whether that is
   because the field is stable or because the corpus was too small to detect
   it. The report gives you the number that settles this.

Then the absolute path to `report.html`.

Keep it to what the evidence supports. If the corpus was thin, say so first
rather than in a footnote.
