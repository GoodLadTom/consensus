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

**Over ~800 claims:** shard by theme.

Ask one agent to read a sample of a few hundred claim texts and propose 10-14
domains, each with the vocabulary that actually appears in those claims. Do
not hand-write the domains yourself: a hand-written set for the lead-generation
corpus left 36% of claims unrouted, because real claims say "coiling the
spring" and "reply early to new forum threads" rather than the words you would
think of. An agent reading actual claims picks those up.

Then route deterministically — no model needed:

```bash
python3 scripts/shard_claims.py \
  --claims "$RUN/claims.json" --domains "$RUN/domains.json" \
  --out-dir "$RUN/shards"
```

It prints each shard's size, the share that matched nothing, and a sample of
unrouted claims. **The largest shard is what the slowest designer reads, so
that number is the one to drive down.** On the lead-generation corpus, twelve
domains took the largest shard from 1,623 claims to 391 — the catch-all — and
anything over about a quarter unrouted means the catch-all has just become the
bottleneck you were trying to remove. Widen the domains the sample points at
and run it again; it costs seconds.

Then run one designer per shard **in parallel**, each producing positions only
for its own claims. Finish with a single merge agent that sees only the
position labels — never the claims — and collapses genuine cross-domain
duplicates. The merge is cheap because it reads a few hundred labels rather
than thousands of claims.

**Tell each designer how many positions its shard should yield.** This is the
one instruction that sharding cannot do without, and leaving it out was
measured: fourteen designers left to their own judgement produced 900
positions where a single designer over the same claims produced 220. A
designer seeing only its own 150 claims splits hairs that do not matter at
corpus scale, because nothing in its view says what level of detail the corpus
can support.

That matters more than it sounds. The report only calls a position a consensus
when at least two independent channels back it, so a taxonomy four times too
fine fragments the support and the whole report reads "not enough evidence".
Faster and worse is not a trade worth making.

Calibrated on the first full run, **about 7 claims per position** is right.
Give each designer a target of `shard_size / 7`, with a band of roughly ±25%
around it, and say explicitly that contradictions are exempt — two sides of a
real disagreement are never merged to hit a number.

**Expect designers to overshoot the target, and do not correct them for it.**
Measured on three shards, the instruction cut 210 positions to 78, a 2.7x
reduction, landing at 4.9 claims per position rather than the 7 asked for.
All three designers gave the same unprompted reason: roughly eleven of their
positions existed only as one half of a disagreement they were forbidden to
merge. A domain where creators argue a lot genuinely needs more positions than
one where they agree, because every disagreement costs two.

That overshoot is a feature. The sharded designers surfaced far more
contradictions than the single pass did, and Contested is one of the sections
the report exists for. Do not tighten the target to chase 7 exactly — you
would be buying tidiness by merging real disagreements, which is the one thing
this pipeline must never do.

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
> 5. Aim for about `N` positions (your shard size divided by seven). Group at
>    the level where several different creators would recognisably be making
>    the same point, not where every nuance gets its own box. Rule 1 overrides
>    this: never merge two sides of a disagreement to hit the number.

## 4.2 Merge the shards

```bash
python3 scripts/merge_taxonomy.py \
  --shard-dir "$RUN/shards" --claims "$RUN/claims.json" \
  --out "$RUN/taxonomy.json"
```

It combines the per-domain files, makes contradictions symmetric, drops
cross-domain references that cannot resolve, and reports the two things worth
a human eye:

- **Granularity.** Claims per position against the target of 7. Too fine and
  it tells you how many positions to aim for on a re-run; too coarse and the
  positions have become topics.
- **Cross-domain near-duplicate labels.** Designers cannot see each other, so
  two can land on the same idea from different angles. Send only those pairs —
  labels and descriptions, never the claims — to one merge agent. That is what
  keeps the merge cheap. On the live run there were none, which is the
  sharding working.

## 4.3 Check the taxonomy before routing anything through it

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

## 4.4 Assign claims to the fixed taxonomy

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

## 4.5 Merge and check

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
