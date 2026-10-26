# Qloo API notes

## Known facts (from the hackathon developer guide, read in Phase 0)
- **Base URL:** `https://hackathon.api.qloo.com`. Hackathon keys get a 401 on staging/production.
- **Auth:** header `X-Api-Key: <key>`. No Bearer tokens, no query-param key.
- **Endpoints:** `/v2/insights` (GET, query params, main recommender), `/search` (name → entity ID), `/v2/tags` (find tag IDs).
  - Don't use `/recommendations` or `/recs` (legacy). `/v2/insights/search` is not a real path.
- **Supported `filter.type`:** `urn:entity:artist`, `book`, `brand`, `destination`, `movie`, `person`, `place`, `podcast`, `tv_show`, `video_game`.
  - Music = `artist`. Food/drink = `place` or `brand`. A 403 on a type means it's unsupported.
- **Signals and filters mentioned:** `signal.interests.entities`, `signal.interests.tags`, `signal.demographics.audiences`, `filter.tags`.
  - Tags and audiences must be **real Qloo IDs/URNs**, not free text. Resolve them via `/v2/tags` first.
- ⚠️ **Invalid params are silently ignored.** A 200 with empty or unchanged results usually means a bad param for that type.
- **Rate limits:** no published numbers; "high enough for typical projects". Ask in Discord `#api-help` to raise them.
- **Caching:** private server-side caching is allowed with no time limit. **Never put Qloo response data in the public repo.**
- Responses contain verbose fields (e.g. `akas`). Trim them before passing to the LLM.
- Keys work through judging and are deactivated after the hackathon.

### Error cheat sheet
| Symptom | Likely cause |
|---|---|
| 401 | wrong base URL, or header not `X-Api-Key` |
| 404 / "No path matching request parameters" | wrong path or POST used (insights is GET) |
| 403 on a type | unsupported `filter.type` |
| "at least one valid signal or filter is required" | invalid tag/audience IDs |
| 200 with empty `entities` | invalid params for the type, or no data for that region; broaden |

## Open questions for Phase 1 (answer with real calls, record results here)
1. `urn:entity:destination`: which signals change the ranking? Does `signal.interests.entities` with movie/artist IDs give clearly different cities for different personas?
2. `urn:entity:place`: how is the location set (city name query? lat/lng + radius?). Which param names exactly?
3. Which tag URNs exist for place categories (restaurant, café, bar, museum, hotel, park, nightlife)? Can we filter by them?
4. Are lat/lng, address, price level and images returned for places (for map pins and cards)?
5. What does the affinity/score field look like, and is it comparable across requests (needed for group fairness ranking)?
6. Can we get tag metadata explaining *why* an entity matches (for "why this matches you")?
7. Coverage: Tokyo, Lisbon, NYC, Mexico City, Bengaluru, Goa, Jaipur. Where is the data thin?
8. Do multiple people's signals in one request blend, or do we need one request per person and merge them ourselves?
9. Latency per call (sets how much we parallelise and cache).
10. Which `signal.demographics.audiences` values exist, and are they useful (e.g. age groups for a family trip)?

## Param allow-list per filter.type (build in Phase 1)
| filter.type | Verified params | Notes |
|---|---|---|
| destination | | |
| place | | |
| artist / movie / … (inputs only via /search) | | |
