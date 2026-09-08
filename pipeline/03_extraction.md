# Phase 3 — Extraction

**Input:** `$RUN/corpus.json`, `cache/*.txt` · **Output:** `$RUN/claims.json`

Pull the specific claims out of every transcript. This phase decides the
quality of everything downstream: vague extraction produces a report full of
positions like "consistency matters", which is true, useless, and agreed on by
everyone.

## What counts as a claim

A claim is **specific enough to be wrong**.

| Extract | Skip |
|---|---|
| "Put the hook in the first 3 seconds" | "The intro is important" |
| "Upload twice a week, not daily" | "Be consistent" |
| "Faces in thumbnails beat text" | "Thumbnails matter a lot" |
| "The algorithm optimises for satisfaction surveys, not watch time" | "The algorithm is complicated" |
| "Shorts views don't feed your long-form recommendations" | "Shorts are different" |

Also take:

- **Numbers** — durations, frequencies, thresholds, percentages
- **Mechanism claims** — how the speaker says the thing works
- **Prohibitions** — "never do X", which cluster against the tactics
- **Explicit reversals** — "this used to work, it doesn't now". These are gold:
  a creator naming dead advice directly.

Ignore: channel promotion, sponsor reads, personal anecdote with no
generalisation, and anything the speaker attributes to someone else without
endorsing.

## How to run it

Batch the corpus into groups of about 10 videos and spawn one subagent per
batch, in parallel, in a single message. For each video the agent reads
`cache/<id>.txt` and returns claims.

Read those files with the Read tool, not `cat`. YouTube video ids can start
with a hyphen (`-fS8na576Jc`), which shell tools read as a flag and choke on.

Give every agent this contract:

> For each video, read `cache/<video_id>.txt`. Extract every claim that is
> specific enough to be wrong. For each claim return:
>
> - `id` — `"<video_id>#<n>"`, n counting from 0 within that video
> - `video_id`
> - `text` — the claim in one neutral sentence, in your words. Not a summary
>   of the video. Written so it can be compared with the same claim made by a
>   different creator in different words.
> - `quote` — verbatim from the transcript, under 30 words, the words that
>   actually make the claim
> - `t` — the `[mm:ss]` marker at or just before the quote
> - `type` — `tactic` | `mechanism` | `number` | `prohibition` | `reversal`
>
> Expect 5-20 claims from a normal video. Under 3 usually means the transcript
> is a vlog rather than advice — return `"skipped": true` with a reason
> instead of straining for claims. Never invent a quote: if you cannot find
> the words in the transcript, drop the claim.

Merge the agent outputs into:

```json
{"claims": [{"id": "...", "video_id": "...", "text": "...", "quote": "...", "t": "03:12", "type": "tactic"}],
 "skipped": ["<video_id>", "..."]}
```

**`skipped` is not optional.** It lists every video an agent read and got
nothing from. Phase 5 tests whether a position has gone quiet, and that test
divides by how many videos were actually read — a video nobody opened is not
evidence that nobody said the thing. Leave a video out of both lists and it is
correctly excluded from the maths; put it in `skipped` and its silence counts.
Getting this wrong invents expired advice out of nothing, so if a batch agent
fails, re-run it rather than proceeding with a gap.

## Check before moving on

```bash
python3 scripts/verify_claims.py \
  --corpus "$RUN/corpus.json" --claims "$RUN/claims.json" --require-coverage
```

This checks every quote appears in its transcript, every id is unique and
well-formed, and every fetched video was either mined or explicitly declared
skipped.

**Exit codes:** `0` clean · `1` bad quotes or malformed claims · `2` coverage
gate — videos were fetched but never reported on.

Do not continue on a non-zero exit.

- **Exit 2** means an extraction batch silently dropped videos. Re-run those
  batches. Every video the corpus paid for must be read, or the absence test
  in Phase 5 loses the power that makes `expired` possible at all. This is the
  gate that stops a hundred-video corpus quietly becoming a sixty-video one.
- **Exit 1** means a quote could not be found in its transcript. A fabricated
  quote reaching the report is the one failure that discredits the whole
  thing, so fix these rather than stripping them, unless the agent clearly
  paraphrased and the claim is sound.
