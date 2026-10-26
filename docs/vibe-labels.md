# Vibe labels (fixed vocabulary)

Used by photo input (Gemini structured output enum) and free-text vibe words. In Phase 1, each label is mapped to one or
more real Qloo tag URNs via `/v2/tags`. Never pass a label to Qloo directly.

| Group | Labels |
|---|---|
| Setting | beach, mountains, countryside, big-city, old-town, waterfront, desert, forest, island |
| Mood | cozy, romantic, lively, quiet, artsy, luxurious, rustic, quirky, minimalist, moody |
| Food & drink | street-food, fine-dining, cafe-culture, coffee, wine, craft-beer, cocktails, vegetarian-friendly, seafood, bakery |
| Activities | nightlife, live-music, museums, galleries, shopping, vintage, markets, hiking, wellness, architecture, history |

40 labels total. Qloo tag mapping: see `qloo-notes.md` → Phase 1.
