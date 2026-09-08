# Phase 0 — Scoping

**Output:** `$RUN/scoping.json`

Turn the user's topic into search queries. This decides the whole corpus, so
it is worth thinking about rather than pasting the topic in eight times.

## Write 8-12 queries

Cover the topic the way different creators would title a video about it. Vary
along these lines:

- **Plain** — how someone would search it: `how to grow on youtube`
- **Outcome** — the result people want: `get more views on youtube`
- **Mechanism** — the machinery: `youtube algorithm explained`
- **Sub-topics** — the parts of the field: `youtube thumbnail tips`,
  `youtube retention`, `youtube seo`
- **Audience** — who is asking: `grow small youtube channel`,
  `youtube for beginners`
- **Contrarian** — where disagreement lives: `youtube advice that is wrong`,
  `stop doing this on youtube`

Rules:

- **No year in the query.** `youtube algorithm 2026` filters out exactly the
  older videos the age comparison depends on. Recency is handled at search
  time by the date-filtered bucket, not by the words.
- Keep queries distinct. Eight phrasings of one query gives one bucket of
  results and a false signal that many videos "agree".
- Match the user's actual field. Do not silently broaden `youtube shorts
  retention` into `youtube growth`.

Write:

```json
{"topic": "<the user's topic, verbatim>",
 "slug": "<kebab-case>",
 "queries": ["...", "..."]}
```

Then tell the user the queries in one line each and move straight on. Do not
stop for approval unless the topic was genuinely ambiguous.
