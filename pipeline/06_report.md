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

## Then tell the user, in the chat

Print the findings — do not just hand over a file path. Give them:

1. **The headline consensus** — the three or four strongest settled positions,
   in plain language, with how many channels back each.
2. **Anything expired** — stated as "creators used to say X; none of the N
   recent videos do". This is the part they cannot get anywhere else, so lead
   with it if it is interesting.
3. **The real disagreements** — where credible people contradict each other,
   stated as a disagreement rather than averaged away.
4. **What the corpus could not tell you** — videos dropped, whether the old
   half was big enough to make the absence test meaningful, and any query that
   returned thin results.

Then the absolute path to `report.html`.

Keep it to what the evidence supports. If the corpus was thin, say so first
rather than in a footnote.
