# Phase 1 runbook: Qloo for tour planning

Run from the repo root (`uv` installs dependencies). Raw responses are cached in `qloo_responses/` (git-ignored, **never commit**).
Write only *findings* into `docs/qloo-notes.md`.

## Done ✅ (27 Oct)
- `check_keys.py`: Qloo ✓, Gemini listing ✓ (main alias returned 503 once), Groq pending
- `hypothesis` → PASS, mean overlap 0.19
- `probe openers`, `heatmap Hovvdy Ohio`, `openers Hovvdy Columbus`
- Artist coverage 27/30

## To do
```bash
# 0. Groq key, then re-check all keys
uv run scripts/check_keys.py

# 1. Remaining probes → fill the allow-list in qloo-notes.md
uv run scripts/qloo_explore.py probe venues
uv run scripts/qloo_explore.py probe sponsors
uv run scripts/qloo_explore.py probe heatmap

# 2. Coverage outside the US (India, UK, EU)
uv run scripts/qloo_explore.py coverage Mumbai Bengaluru Delhi Pune London Berlin --artist "Prateek Kuhad"
uv run scripts/qloo_explore.py coverage --artist "Hovvdy"

# 3. Sounds-like heatmap (artist not on Qloo): comma-separate several IDs
uv run scripts/qloo_explore.py search "Prateek Kuhad" --types urn:entity:artist
uv run scripts/qloo_explore.py shape filter.type=urn:heatmap signal.interests.entities=<id1>,<id2>,<id3> filter.location.query=India

# 4. Promo spots
uv run scripts/qloo_explore.py tags "record store"
uv run scripts/qloo_explore.py tags "coffee shop"

# 5. Sponsors per city
uv run scripts/qloo_explore.py sponsors "Hovvdy" --city Columbus

# 6. Opener cap for a small headliner
uv run scripts/qloo_explore.py openers "Divino Niño" Chicago
```

## Done when
- [ ] Allow-list complete for heatmap, artist, place, brand
- [ ] India/EU coverage noted (which demo personas to feature)
- [ ] Sounds-like heatmap behaviour noted
- [ ] Promo tag IDs listed
- [ ] `git status` shows **no** files from `qloo_responses/`
