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

## Param allow-list per filter.type ✅ complete
| filter.type | Verified working | Verified ignored / invalid / harmful |
|---|---|---|
| `urn:heatmap` | `signal.interests.entities` (one **or several**, comma-separated), `filter.location.query` (country / state / city) | no artist signal → **400**; `signal.demographics.age` → 7,401 cells in 14 s, ignores the region → **don't use** |
| `urn:entity:artist` | `signal.interests.entities`, `signal.location.query`, `signal.location.weight`, `filter.popularity.max`, `signal.interests.tags`, `feature.explainability`, `take` | `filter.location.query` (ignored), `signal.location.radius` (ignored) |
| `urn:entity:place` | `signal.interests.entities` (changes ranking, overlap 0.36 without it), `filter.location.query`, `filter.tags`, `feature.explainability`, `take` | `filter.rating.min` (ignored), `signal.location.radius` (ignored), `filter.popularity.max` → **pulls in restaurants, don't use for venues** |
| `urn:entity:brand` | `signal.interests.entities`, `signal.location.query` (overlap 0.30 Chicago / 0.36 Austin), `signal.demographics.age` (0.58), `bias.trends` (0.76), `feature.explainability`, `take` | |
| `urn:entity:destination` | works but not useful | |
| `urn:entity:locality` | — | 400 on insights |

### Heatmap resolution adapts to the region ⭐
- `United States` → geohash-**4** cells (~40 km) · `Texas` → geohash-**5** (~5 km) · `Chicago` → geohash-**7** (~150 m, 314 cells).
- So the same tool gives **metro ranking** (country/state query) and **neighbourhood hot spots** inside a city (city query) for the flyer/promo map.

### Sounds-like heatmap (artist not on Qloo) ✅
`signal.interests.entities=<Prateek Kuhad>,<When Chai Met Toast>,<Anuv Jain>` + `filter.location.query=India` → 3,101 cells in 1.2 s.
- Top (affinity × popularity): Bengaluru, Mumbai, Delhi, Kolkata, Goa, Pune → sensible for Indian indie.
- Overlap with each single artist: 0.67 / 0.35 / 0.67 → it really **blends** the signals; no artist dominates. Use 2–4 sounds-like IDs.

### Coverage outside the US
| City | Venues | Top venue | Openers | Top opener | Verdict |
|---|---|---|---|---|---|
| Chicago / Columbus / Madison / Austin (Hovvdy) | 20–30 | Burlington Bar, Rumba Café, The Wisco, Hotel Vegas | 10 | Knox Fortune, Snarls, Disq, Duncan Fellows | ✅ real indie rooms, local openers |
| London / Berlin (Hovvdy) | 30 | The Shacklewell Arms, Schokoladen | 10 | 00110100 01010100 | ✅ venues good, openers weaker |
| Mumbai / Bengaluru / Delhi / Pune (Prateek Kuhad) | 12–17 | Roaring Farm, Fandom at Gilly's, Piano Man Jazz Club, BMG Unplugged | 10 | Jasleen Royal (3 cities), When Chai Met Toast | ⚠️ venues OK; same national act tops several cities → not local |
| London (Prateek Kuhad) | 30 | Dawat Bar and Kitchen (Indian restaurant) | 10 | Moxie | ⚠️ diaspora signal pulls in restaurants |

→ **Demo personas:** lead with US (Hovvdy Midwest, Men I Trust), then one India persona to show reach. Venue tags must stay on
(`live_music_venue` + `music_venue`) to keep restaurants out, and the opener list needs a de-dupe: **an act that tops ≥ 3 cities is
"national", not "local"**.

### Promo spots ✅
| Tag ID | Chicago results for Men I Trust fans |
|---|---|
| `urn:tag:category:place:record_store` | Shuga Records, Dusty Groove, Gramaphone Records, Laurie's Planet of Sound, Bucket O' Blood |
| `urn:tag:category:place:book_store` | Quimby's Bookstore, Uncharted Books, Laurie's Planet of Sound |
| `urn:tag:category:place:coffee_shop` | Drip Collective, Loba Pastry + Coffee, The Book Cellar (+ noise: "Chicago", an arts centre) |
| `urn:tag:category:place:bar` | (ID verified, not yet ranked) |
Use `category:` tags (not `genre:`/`nearby:`); drop results with no address (the "Chicago" entity).

### Sponsors per city ✅
Hovvdy national → … Cold Picnic. **Columbus** → Baggu, Need Supply Co., Entireworld, Everlane, Lacausa… new in Columbus: Everlane,
Noto Botanics, Tradlands. Smaller DTC brands are realistic sponsor targets for a mid-sized act (unlike Urban Outfitters).

### Opener cap for a small headliner (Divino Niño .782, Chicago, cap .732)
KAINA, Ohmme, Peter CottonTale, Femdot, Joseph Chilliams, CEP, Bump J, Tatiana Hazel (8/10 Chicago ✓) + Dita Von Teese, Jack Antonoff (✗).
- −0.05 margin is fine. Locality is good, but **genre drifts to Chicago hip-hop** → add a **fit score** = affinity of the opener in a
  no-location run for the same headliner, and rank by `0.6·fit + 0.4·local affinity`. Jack Antonoff showing up twice (Columbus,
  Chicago) confirms the "national act" de-dupe and the MusicBrainz badge.

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

## Phase 2 findings (27 Oct, building the MCP server)
- `GET /entities?entity_ids=<id>` works (returns the full entity incl. `popularity` and tags). `/v2/entities` → 404.
- `take` max is **50** (`take=100` → 400). Enforced in the allow-list.
- Insights artist results carry ~50 tags; genre tags sometimes name the city (`Chicago`, `Chicago Hip Hop`) → a free locality hint.
- A no-location "fit" run (headliner signal + popularity cap, take 50) for Divino Niño contained **none** of the 15 local
  openers → fit is computed from genre-tag overlap instead.
- `filter.location.query=Midwest` → **0 cells**; regions must be expanded to states (done in `demand_map`).
- Hovvdy Midwest (12 states, 3.8 s in parallel): Chicago, Lawrence KS, Detroit, Columbus, Des Moines, Bloomington IN,
  Minneapolis, Eau Claire WI… college towns surface as intended. Demand scores are compressed (86–100 for the top 12) and
  single-cell metros with affinity 1.0 rank high → tune in Phase 3 (min cells / activity weight).
- MusicBrainz: Knox Fortune, Divino Niño, KAINA, Snarls, Vesperteen, Disq → based here ✓; Noah Reid → Toronto (elsewhere ✓);
  Jack Antonoff → Bergen County (unknown); NNAMDÏ → Los Angeles (elsewhere ✗, he's a Chicago act: MusicBrainz data, track in the eval).
  MusicBrainz returns 503 "busy" under load → retry with backoff.

## Still open → moved to Phase 3 (scoring tuning)
1. Fit-score weights for openers (0.6/0.4 is a first guess) → tune on the opener-fit eval.
2. Population weighting for heatmap cells (GeoNames metro population) → check that Athens OH still ranks.
3. Screenshot reader needs a sample streaming-dashboard image.
