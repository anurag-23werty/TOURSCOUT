# Wireframes (low-fi)

Four screens plus a compare tab. Mobile stacks the columns vertically.

## 1. Home
```
┌──────────────────────────────────────────────────────────────┐
│ 🧭 TourScout                               [Compare] [GitHub] │
│                                                              │
│     Trips planned from what you actually love.               │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ I love Interstellar, Arctic Monkeys, ramen, Muji…       │  │
│  │ 3 days · mid budget · from Bengaluru            [ Go → ]│  │
│  └────────────────────────────────────────────────────────┘  │
│   [ Solo ]  [ Group 👥 ]          📷 photos (stretch) 🎙 (stretch) │
│                                                              │
│  Try a persona:                                              │
│  [🎬 Film nerd] [🍜 Foodie] [🎸 Indie fan] [👥 4 friends]     │
└──────────────────────────────────────────────────────────────┘
```

## 2. Confirm taste (human-in-the-loop #1)
```
┌───────────────────────────────┬──────────────────────────────┐
│ We understood your taste as:  │  Agent timeline (live)        │
│                               │  ✓ Extracted 4 interests      │
│ [🎬 Interstellar (movie) ✕]   │  ✓ search "Arctic Monkeys"    │
│ [🎸 Arctic Monkeys (artist)✕] │    → artist                   │
│ [🍜 ramen → tag ✕]            │  ✓ search_tags "ramen"        │
│ [🏷 Muji (brand) ✕]           │  ⏸ waiting for you            │
│ Did you mean "Dune" the book? │                              │
│ [ + add ]       [ Looks right → ]                            │
└───────────────────────────────┴──────────────────────────────┘
```

## 3. Destinations (human-in-the-loop #2)
```
┌──────────────────────────────────────────────────────────────┐
│ Destinations that match you                                  │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐                       │
│ │ Tokyo    │ │ Seoul    │ │ Berlin   │                       │
│ │ ▓▓▓▓▓ 92 │ │ ▓▓▓▓░ 85 │ │ ▓▓▓▓░ 81 │                       │
│ │ Why: sci-│ │ Why: …   │ │ Why: …   │                       │
│ │ fi film  │ │          │ │          │                       │
│ │ culture, │ │          │ │          │                       │
│ │ minimal… │ │          │ │          │                       │
│ │ [Plan →] │ │ [Plan →] │ │ [Plan →] │                       │
│ └──────────┘ └──────────┘ └──────────┘                       │
│ Group mode: per-person bars  Asha ▓▓▓▓  Ravi ▓▓▓░  Meera ▓▓▓▓ │
└──────────────────────────────────────────────────────────────┘
```

## 4. Trip
```
┌──────────────────────────────┬───────────────────────────────┐
│ Tokyo · 3 days               │                               │
│ Day 1 ─────────────────────  │         🗺  MAP               │
│ ☀ Morning  Café X      [why] │     📍1   📍2                 │
│ 🌤 Afternoon Museum Y  [why] │          📍3                  │
│ 🌙 Evening  Bar Z      [why] │                               │
│ Day 2 … Day 3 …              │                               │
│                              │                               │
│ 💬 "make day 2 more chill"  [send]                           │
│ Timeline ▸ (collapsible)     │   [Share] [Compare with LLM]  │
└──────────────────────────────┴───────────────────────────────┘
```
`[why]` expands: "Because you like **Arctic Monkeys** and **Muji** → Qloo tags: *indie, minimalist, vinyl* · affinity 0.87".

## 5. Compare
```
┌─────────────────────────────┬────────────────────────────────┐
│ LLM only                    │ TourScout (Qloo-grounded)       │
│ Day 1: Senso-ji, Shibuya    │ Day 1: Café X, Museum Y …       │
│ "Cafe Lumiere" ⚠ not found  │ ✓ all 12 places verified        │
│ generic, popularity-based   │ per-pick taste explanation      │
│ Grounded: 7/12              │ Grounded: 12/12                 │
└─────────────────────────────┴────────────────────────────────┘
```
