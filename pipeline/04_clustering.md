# Phase 4 — Clustering

**Input:** `$RUN/claims.json` · **Output:** `$RUN/clusters.json`

Group claims that make the same point in different words. Ten creators saying
"hook them in the first three seconds" must become one position with ten
backers, not ten positions with one each.

This runs in two passes: one agent designs the positions, then parallel agents
file claims into them. Doing it in one pass does not work at real corpus size,
and doing the design in parallel produces near-duplicate positions that then
have to be merged by hand.

## Sizing, measured

On a 105-video run: 1,623 claims, 220 positions. A single agent designing that
taxonomy took **30 minutes — 42% of the entire pipeline**, and it is the only
stage with no parallelism. If the run feels slow, this is why.

Shard it (see 4.1) when the claim count is over about 800. Below that, one
agent is simpler and fast enough.

## 4.1 Design the positions

Write a slim view first — id and text only, no quotes. Quotes triple the token
cost and add nothing to the design decision.

**Under ~800 claims:** one agent over the whole list.

**Over ~800 claims:** shard by theme. Ask one cheap agent to read the claim
texts and propose 5-8 broad domains (for a lead-generation corpus: cold email,
cold calling, paid ads, SEO, referrals and partnerships, offers and pricing,
content and organic). Split the claims by domain, then run one designer per
domain **in parallel**, each producing positions only for its own claims.
Finish with a single merge agent that sees only the position labels — never
the claims — and collapses genuine cross-domain duplicates. The merge is
cheap because it reads a few hundred labels rather than thousands of claims.

Give each designer this contract:

> Design the set of **positions** these claims fall into. You are producing
> the taxonomy only; a later pass assigns claims to it.
>
> A position is a **claim about the world that could be wrong**, not a topic.
> "Cold email" is a topic and is wrong. "Follow-ups, not the first email,
> produce most booked meetings" is a position.
>
> For each: `id` (kebab-case), `label` (the position stated as a claim, in
> plain language), `description` (one or two sentences, including any
> disagreement among its supporters), `keywords` (the vocabulary creators
> actually use for it, including synonyms), and `contradicts` where two
> positions genuinely conflict.
>
> Rules:
> 1. **Opposites do not merge.** "Follow the script word for word" and
>    "scripts sound robotic, work from a framework" are two positions that
>    contradict, not one position about scripts. Record it on both.
> 2. **Do not merge a specific claim into a general one.** "Send 100 cold
>    emails a day" is not "do high-volume outreach".
> 3. **Every keyword must be distinctive.** Assignment routes on keywords, so
>    a phrase on two positions sends claims to whichever listed it rather than
>    whichever means it. Do not put "lifetime value" on three positions.
> 4. Cover the whole space. Singletons are fine — they become the outliers.
> 5. Let the material decide the count. Do not aim for a number.

## 4.2 Check the taxonomy before routing anything through it

```bash
python3 scripts/check_taxonomy.py --taxonomy "$RUN/taxonomy.json"
```

Reports duplicate ids and labels, dangling and one-sided `contradicts`,
positions with no keywords, keyword collisions, and positions with no
distinctive keyword at all.

Measured on the first live run: 55 colliding keywords of 1,980 distinct
(2.8%), no positions left unroutable. That is the level to expect and roughly
the level to accept. Fix collisions on the positions the assignment agents
later name as weak; do not chase every one.

## 4.3 Assign claims to the fixed taxonomy

Split the claims into batches of about 200 and run one agent each, in
parallel. They may **not** invent positions.

> Assign every claim to exactly one position id from the taxonomy. Route on
> `keywords`. Pick the **most specific** position that genuinely fits.
>
> **Never file a claim into a position it contradicts.** If a claim says
> "scripts sound robotic" it goes to the framework position, not the
> word-for-word one.
>
> If a claim genuinely fits nothing, assign `"unassigned"`. Use it sparingly —
> a real misfit, not a hard judgement call.
>
> Output a flat `{"<claim id>": "<cluster id>"}` mapping and nothing else.
> Verify it has exactly as many keys as your input had claims.

Ask each agent to report which positions it found ambiguous or overlapping.
That feedback is the cheapest source of taxonomy repairs you will get, and it
comes from agents that have just read 200 real claims against it.

## 4.4 Merge and check

```bash
python3 scripts/merge_clusters.py \
  --claims "$RUN/claims.json" --taxonomy "$RUN/taxonomy.json" \
  --batch-dir "$RUN/batches" --out "$RUN/clusters.json"
```

It exits non-zero and tells you what to do when any of the following is true.
Verify before moving on:

- **Every claim mapped exactly once**, and every value a real position id.
- **Unassigned under about 3%.** The first live run came in at 1.4% (22 of
  1,623), and reading those 22 is worth the minute it takes — they name the
  gaps in the taxonomy. On that run they were genuinely off-topic (agency
  workload, a bare definition of outbound, team headcount) rather than
  missing positions.
- **No runaway cluster.** One position holding more than about a fifth of all
  claims is a topic that has swallowed several positions. The first live run
  topped out at 32 claims of 1,623, which is healthy.
- Read the members of the two or three largest. If two random members are not
  making the same point, split it.
