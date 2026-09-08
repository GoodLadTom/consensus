# Phase 1 — Discovery

**Input:** `$RUN/scoping.json` · **Output:** `$RUN/candidates.json`

```bash
python3 scripts/discover.py \
  --queries "$(python3 -c 'import json;print(json.dumps(json.load(open("'"$RUN"'/scoping.json"))["queries"]))')" \
  --target 140 --per-query 16 \
  --out "$RUN/candidates.json"
```

The target is 140 candidates for a 100-transcript corpus. That headroom is
not padding: some videos have no captions, and some are lost to rate limiting
even with the fetcher pacing itself. Measured loss on a live run was 5%, and
caption-less videos come on top of that. Fetching stops the moment 100
transcripts are in hand, so surplus candidates cost nothing.

Each query is run twice: once on plain relevance, once constrained to the last
year. That is what produces a corpus with both halves in it.

## Check before moving on

The script prints `pool=N chosen=N (recent-only=N in-both=N)`.

- **`recent-only` is 0** — the date-filtered bucket returned nothing new.
  Either the topic is quiet on YouTube, or the queries are so specific that
  only the same few videos rank. Broaden a couple of queries and re-run.
- **`pool` barely exceeds `chosen`** — not enough candidates to be selective.
  Add queries rather than raising `--per-query`, which just digs deeper into
  the same ranking.
- **`in-both` is nearly everything** — the topic has little recent activity.
  Worth saying in the report; the age comparison will be weak.

Videos under two minutes and over two hours are dropped before any request is
spent on them.
