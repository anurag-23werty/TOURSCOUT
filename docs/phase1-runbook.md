# Phase 1 runbook: the day the Qloo key arrives

Run everything from the repo root. `uv` installs the dependencies automatically.
Raw responses are cached in `qloo_responses/` (git-ignored, **never commit**). Only write *findings* into `docs/qloo-notes.md`.

## Step 0: keys (5 min)
```bash
cp .env.example .env        # fill in QLOO_API_KEY, GEMINI_API_KEY, GROQ_API_KEY
uv run scripts/check_keys.py
```
Copy the model lines and Groq limits into `docs/models.md`.

## Step 1: the core bet (10 min) ← most important
```bash
uv run scripts/qloo_explore.py hypothesis
```
Four contrasting personas → top-10 destinations each → pairwise overlap.
- **PASS (mean overlap < 0.5):** carry on.
- **FAIL:** try adding `signal.interests.tags`, `bias.trends`, or fewer/more entities. If it still fails, we rethink the pitch *today*, not in week 3.

## Step 2: what the data looks like (15 min)
```bash
uv run scripts/qloo_explore.py shape filter.type=urn:entity:place filter.location.query=Tokyo take=30
uv run scripts/qloo_explore.py shape filter.type=urn:entity:destination signal.interests.entities=<id> take=10
uv run scripts/qloo_explore.py shape --path /search query=Tokyo types=urn:entity:locality
```
Answers Q4 (lat/lng, price, images, tags on places?), Q5 (affinity format), Q6 (explainability).

## Step 3: which params really work (20 min)
```bash
uv run scripts/qloo_explore.py probe destination
uv run scripts/qloo_explore.py probe place
```
`CHANGED` = the param works. `IGNORED?` = probably invalid for this type (Qloo ignores bad params silently). `EMPTY` = too strict.
Fill in the **param allow-list** table in `qloo-notes.md`. This becomes the validation list in the Phase 2 MCP server.

## Step 4: tags and categories (20 min)
```bash
uv run scripts/qloo_explore.py tags coffee
uv run scripts/qloo_explore.py tags restaurant
uv run scripts/qloo_explore.py tags museum --param filter.tag.types=urn:tag:category:place   # try variants if the plain call doesn't work
```
Map each label in `docs/vibe-labels.md` to 1–3 real tag URNs (keep the mapping table in `qloo-notes.md`).
Answers Q3 (place category tags).

## Step 5: coverage and latency (10 min)
```bash
uv run scripts/qloo_explore.py coverage
uv run scripts/qloo_explore.py coverage Kyoto Berlin Hampi
```
Answers Q7 (where data is thin) and Q9 (latency). Choose demo personas and destinations with strong coverage.

## Step 6: group blending (15 min)
Run `insights` for one destination with persona A's IDs, persona B's IDs, and both together:
```bash
uv run scripts/qloo_explore.py insights filter.type=urn:entity:place filter.location.query=Lisbon signal.interests.entities=<A ids>
uv run scripts/qloo_explore.py insights filter.type=urn:entity:place filter.location.query=Lisbon signal.interests.entities=<B ids>
uv run scripts/qloo_explore.py insights filter.type=urn:entity:place filter.location.query=Lisbon signal.interests.entities=<A ids>,<B ids>
```
Answers Q8: does one combined request blend fairly, or do we need per-person requests and our own fairness ranking? (The plan assumes the latter.)

## Done when
- [ ] Every question in `qloo-notes.md` has an answer
- [ ] Param allow-list filled for `destination` and `place`
- [ ] Vibe label → tag URN mapping done
- [ ] Hypothesis PASS recorded with the number
- [ ] `git status` shows **no** files from `qloo_responses/`
