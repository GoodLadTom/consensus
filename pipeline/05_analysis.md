# Phase 5 — Analysis

**Input:** corpus, claims, clusters · **Output:** `$RUN/analysis.json`

Deterministic. No model involved — this is the arithmetic the report rests on.

```bash
python3 scripts/analyse.py \
  --corpus "$RUN/corpus.json" \
  --claims "$RUN/claims.json" \
  --clusters "$RUN/clusters.json" \
  --out "$RUN/analysis.json"
```

Options worth knowing:

| Flag | Default | Effect |
|---|---|---|
| `--half-life` | 1.5 | Years for a claim's weight to halve |
| `--recent-months` | 12 | Where the recent/old line falls |
| `--min-backing` | 2 | Distinct channels before any status is assigned |
| `--alpha` | 0.10 | How unlikely an absence must be to count as real |

It prints a summary. Read it before continuing:

- **`expired` is 0** — normal on a stable topic. Do not lower `--alpha` to
  manufacture some. On a fast-moving topic with none, check that Phase 1
  actually gathered old videos (`corpus_old`).
- **Almost everything is `thin`** — the corpus is too small, or clustering was
  too fine and split one position across several clusters.
- **`corpus_old` under about 15** — the absence test has little power, so
  `expired` will rarely trigger. Say this in the report rather than implying
  the field has no dead advice.

The summary reports `corpus_fetched` and `corpus_unread`. If `corpus_unread`
is not zero, extraction did not cover everything that was fetched, and those
videos are excluded from the absence test rather than counted as silence.
That is the safe behaviour; the fix is to finish extraction, not to pass
`--assume-full-coverage`, which exists only for corpora you know were fully
read.

Do not edit `analysis.json` by hand. If a status looks wrong, the fix is in
the clustering or the corpus, not the number.
