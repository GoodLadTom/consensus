# Phase 4 — Clustering

**Input:** `$RUN/claims.json` · **Output:** `$RUN/clusters.json`

Group claims that make the same point in different words. Ten creators saying
"hook them in the first three seconds" must become one position with ten
backers, not ten positions with one each.

## How to run it

One subagent, with the whole claim list in context. It needs to see every
claim at once — clustering in batches produces near-duplicate clusters that
then have to be merged anyway.

Give it this contract:

> Read `$RUN/claims.json`. Group the claims into positions. Two claims belong
> together when a reasonable person would say they make the same point, even
> in different words.
>
> Return for each cluster:
>
> - `id` — kebab-case slug
> - `label` — the position stated as a claim, in plain language. "Hook the
>   viewer in the first 3 seconds", not "Hooks and intros".
> - `description` — one or two sentences on what the position holds, including
>   any disagreement between its members about specifics
> - `claim_ids` — every member claim id
>
> Rules:
>
> 1. **A cluster is a position, not a topic.** "Thumbnails" is a topic and is
>    wrong. "Faces in thumbnails outperform text" is a position.
> 2. **Opposites do not cluster.** "Post daily" and "do not post daily" are
>    two positions that contradict, not one position about frequency. Record
>    the pairing in `contradicts` on both.
> 3. **Do not merge a specific claim into a general one.** "Upload twice a
>    week" is not the same position as "upload consistently".
> 4. Every claim goes to exactly one cluster. Singletons are fine and expected
>    — they become the outliers.
> 5. Do not aim for a cluster count. Let the material decide.

## Check before moving on

- Open two or three of the largest clusters and read their members' quotes.
  If two random members are not making the same point, the cluster is too
  coarse — send it back to be split.
- A cluster holding more than about a third of all claims is almost always a
  topic that has swallowed several positions.
- Every `contradicts` reference should point to a real cluster id.
