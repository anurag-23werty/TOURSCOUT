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

## Param names from the API reference (read Phase 1; still verify with `probe`)
Source: Insights API deep dive + `/search` reference on docs.qloo.com.

**`/search`**: `query`, `types` (comma list), `filter.location` (lat,lon / WKT / entity id), `filter.radius` (**miles**, 0–100, default 10),
`filter.tags`, `filter.rating`, `filter.popularity`, `filter.address`, `operator.filter.tags` (union|intersection), `page`, `take` (<200),
`sort_by` (match|distance|popularity). Response: `{success, duration, results: [...]}`.
- ⚠️ `/search` type names differ from insights: **`urn:entity:videogame`** (insights: `video_game`), and search has **`urn:entity:locality`** (cities, useful for resolving destinations) and `urn:entity:audience`.

**`/v2/insights`** (response `{success, results: {entities: [...]}, duration}`):
- Core: `filter.type`, `take`, `page`, `offset`, `sort_by`, `diversify.by`, `diversify.take`, **`feature.explainability`** (adds `query.explainability`; candidate source for the "why" text)
- Signals: `signal.interests.entities` (+ `.weight`, `.query`), `signal.interests.tags` (+ `.weight`), `signal.demographics.age|gender|audiences` (+ `.weight`), `signal.location`, `signal.location.query`, `signal.location.radius`, `signal.location.weight`
- Location filters: `filter.location` (`"lat,lon"` or `POINT(lon lat)`), `filter.location.query` (e.g. `"New York City"`), `filter.location.radius` (**metres**, e.g. `10000`; `0` = no padding), `filter.location.metro`, `filter.location.geohash`, `filter.exclude.location*`, `filter.geocode.name|admin1_region|admin2_region|country_code`
- Tags: `filter.tags`, `operator.filter.tags`, `filter.exclude.tags`, `filter.results.tags`
- Places: `filter.price_level.min|max`, `filter.hotel_class.min|max`, `filter.hours`, `filter.rating.*`, `filter.popularity.min|max`, `filter.external.tripadvisor.rating.min|max`, `filter.external.resy.*`, `filter.properties.business_rating.*`
- Bias: `bias.trends`, `bias.content_based`, `bias.quality`. Exclusions: `filter.exclude.entities`
- Entity fields mentioned: `query.affinity`, `query.explainability`, `properties.geocode.*` (name, city, country_code, metro…), `properties.image`, `properties.description`
- ⚠️ Radius units differ: search = miles, insights = metres.
- `/v2/tags` params are **not documented on a page we could find**. The explorer assumes `filter.query`; confirm on day 1 (`tags coffee`, then try `--param` variants).

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
