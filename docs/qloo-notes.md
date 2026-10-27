# Qloo API notes

## Basics (hackathon developer guide)
- **Base URL:** `https://hackathon.api.qloo.com`. Hackathon keys get a 401 on staging/production.
- **Auth:** header `X-Api-Key`. GET with query params only (POST on insights = 404).
- **Endpoints:** `/v2/insights` (recommender + heatmap), `/search` (name → entity ID), `/v2/tags` (tag IDs). Not `/recommendations` or `/recs`.
- **Invalid params are silently ignored.** Always verify with `probe`.
- **Caching:** private server-side caching is allowed indefinitely. **Never commit Qloo response data.**
- Trim verbose fields (`akas`, `disambiguation`, `external`, full `hours`) before sending to the LLM.
- Rate limits: no published numbers; ask in Discord `#api-help`.

### Error cheat sheet
| Symptom | Likely cause |
|---|---|
| 401 | wrong base URL, or header not `X-Api-Key` |
| 400 | unsupported `filter.type` value (seen: `urn:entity:locality` on insights) |
| 403 | entity type not enabled for hackathon keys |
| 404 / "No path matching" | wrong path or POST |
| "at least one valid signal or filter is required" | invalid tag/audience IDs |
| 200 + empty | invalid params for the type, or no data; broaden |

---

## ✅ Verified with real calls (27 Oct, Phase 1)

### Artist search
`GET /search?query=<name>&types=urn:entity:artist&take=1` → `results[]` with `entity_id`, `name`, `popularity` (0–1), `tags`, `properties`, `types`.
- Coverage: 27/30 test artists found, incl. Indian indie (Prateek Kuhad .86, When Chai Met Toast .68, Seedhe Maut .59, Thaikkudam Bridge .42).
- **Not found:** Parekh & Singh, Easy Wanderlings, Kayan → these are our "sounds like" fallback test cases.
- Fuzzy matches return a *different* artist (e.g. "Kayan" → Kayano Ai), so **always confirm with the user** (checkpoint 1).
- `/search` type names differ from insights: `urn:entity:videogame` (insights: `video_game`).

### Heatmap = demand map ⭐
`GET /v2/insights?filter.type=urn:heatmap&signal.interests.entities=<artist id>&filter.location.query=<region>`
- Men I Trust, `United States` → **2,532 cells** in 4.2 s. `Texas` → 384 cells in 0.8 s. Prateek Kuhad, `India` → 3,100 cells.
- Cell fields: `location.{latitude, longitude, geohash}` (geohash-4), `query.{affinity, affinity_rank, popularity, entity_artist_affinity, entity_artist_affinity_rank}`.
- ⚠️ Field names differ from entities: heatmap uses `latitude`/`longitude`, entities use `lat`/`lon`.
- ⚠️ Affinity alone favours tiny remote cells (Prateek Kuhad India: Ladakh cells at affinity_rank 1 with popularity 0.05) → **weight by popularity and population** (see ARCHITECTURE §5).
- Men I Trust US top cells: SF Bay, LA, NYC, Seattle; sensible.

### Destination / locality: ❌ not useful for touring
- `urn:entity:destination` for Men I Trust → Shanghai, Hong Kong, Hangzhou… (tourism destinations, not gig markets). Don't use.
- `urn:entity:locality` on insights → **400**. Use the heatmap instead.

### Local openers ⭐
`filter.type=urn:entity:artist` + `signal.interests.entities=<headliner>` + `signal.location.query=<city>` + `signal.location.weight=25` + `filter.popularity.max=0.9`
- Men I Trust, Chicago → Divino Niño, Knox Fortune, Sen Morimoto, Natalie Bergman, NNAMDÏ, KAINA: **all Chicago-based acts**, popularity .68–.83 (below Men I Trust's .99).
- Without the weight/popularity cap → Japanese Breakfast, Crumb, The Marías (similar but too big and not local).
- ⚠️ `filter.location.query` is **ignored** for artists (identical to no location). Use `signal.location.*`.
- Opener sizing: the headliner's own `popularity` from `/search` sets the cap (e.g. headliner − 0.05). Tune in Phase 3.

### Venues ⭐
`filter.type=urn:entity:place` + `filter.location.query=Chicago` + `filter.tags=<tag>` + artist signal
- `urn:tag:category:place:live_music_venue` (same results as `urn:tag:genre:place:live_music_venue`) → The Chicago Theatre, Lincoln Hall, Thalia Hall, Congress Theater, Shuga Records, Rockefeller Chapel.
- `urn:tag:setting:qloo:music_venue` → fewer, more "club" results: Concord Music Hall, Los Globos, Reggies.
- Use both and merge. The results mix room sizes (Chicago Theatre ≈ 3,600 cap) → **Qloo has no capacity field**; show "capacity: verify".
- Place fields: `entity_id, name, location.{lat,lon}, popularity, properties.{address, business_rating, hours, event_spaces, good_for[], ambience_description, customer_demographics_description, geocode.*}, external.google_place`.
- Without a tag, places for an artist's fans are museums/parks (useful for promo spots, not venues).

### Sponsors ⭐
`filter.type=urn:entity:brand` + artist signal (+ optional `signal.location.query=<city>`)
- Men I Trust national → Urban Outfitters .977, Dr. Martens .940, American Apparel .933, Free People .931, Polaroid .930.
- Chicago → Free People, American Apparel, Polaroid, **Herschel Supply Co, VSCO** (new). City signal changes the ranking → "city uplift" is real.

### Tags
`GET /v2/tags?filter.query=<word>&take=<n>` works → `results.tags[]` with `id`, `name`, `type`, `parents[].type`.
- Useful IDs: `urn:tag:category:place:live_music_venue`, `urn:tag:genre:place:live_music_venue`, `urn:tag:setting:qloo:music_venue`,
  `urn:tag:good_for:qloo:live_music`, `urn:tag:category:place:concert_hall`, `urn:tag:genre:music:indie`, `urn:tag:genre:music:indie_rock`.
- `filter.tag.types` didn't return results in our test; leave it out.

### Latency observed
search 0.8–1.5 s · artist/brand/place insights 0.4–3.4 s · heatmap 0.8–4.2 s → parallelise the per-city fan-out and cache heatmaps.

---

## Param allow-list per filter.type (fill from `probe`)
| filter.type | Verified working | Verified ignored / invalid |
|---|---|---|
| `urn:heatmap` | `signal.interests.entities`, `filter.location.query` (country/state) | |
| `urn:entity:artist` | `signal.interests.entities`, `signal.location.query`, `signal.location.weight`, `filter.popularity.max`, `signal.interests.tags`, `feature.explainability`, `take` | `filter.location.query` (ignored), `signal.location.radius` (ignored) |
| `urn:entity:place` | `signal.interests.entities`, `filter.location.query`, `filter.tags`, `take` | |
| `urn:entity:brand` | `signal.interests.entities`, `signal.location.query`, `take` | |
| `urn:entity:destination` | works but not useful | |
| `urn:entity:locality` | — | 400 on insights |

### Hypothesis test ✅ PASS
`qloo_explore.py hypothesis`: top-25 US demand cells for Men I Trust, Thee Sacred Souls, Ed Maverick, Pinegrove →
**mean pairwise overlap 0.19** (lowest: Thee Sacred Souls vs Pinegrove 0.02). Demand maps are artist-specific, not just population.
Cell counts differ a lot (Ed Maverick 830 vs Pinegrove 4,457), so normalise per artist.

### Hovvdy in Ohio (demo check)
Heatmap (61 cells) top: Columbus, Cleveland, Cincinnati, **Athens OH (college town)**. This is exactly the "unserved mid-sized market" story.
Openers in Columbus (cap .847): Snarls, Doc Robinson, Vesperteen (Columbus acts ✓) but also Noah Reid and Jack Antonoff (✗ not local).
→ **Qloo's location signal finds acts popular *in* a city, not acts *from* it. The MusicBrainz "local" badge is required**, and the
opener-locality eval will measure exactly this.

### Opener probe (Men I Trust, Chicago)
| Variant | Result |
|---|---|
| remove location signal / use `filter.location.query` | CHANGED, overlap 0.0 → location signal is what makes openers local |
| default location weight | CHANGED, overlap 0.11 → weight 25 matters a lot |
| no popularity cap | CHANGED, overlap 0.25 → cap removes too-big acts |
| `filter.exclude.entities=<headliner>` | IGNORED? (headliner already removed by the cap, so not conclusive; keep it, it's harmless) |
| `signal.location.radius=30000` | IGNORED? → don't use |
| `signal.interests.tags=genre:indie` | CHANGED, overlap 0.67 → optional genre nudge |
| `feature.explainability=true` | adds `query.explainability.signal…` → **use it for the "why" text** |

## Still open (finish in the runbook)
1. Heatmap with several signal IDs (sounds-like path): does it blend sensibly?
2. Heatmap for a city's metro only (`filter.location.query=Chicago`): resolution good enough for neighbourhoods?
3. `probe venues`, `probe sponsors`, `probe heatmap`.
4. Promo-spot tags: record store, café, bar IDs.
5. India and Europe: `coverage` for Bengaluru, Mumbai, Berlin, London.
6. Opener popularity margin: is −0.05 right for small headliners (Divino Niño .78)?
