# Wireframes (low-fi)

## 1. Home / intake
```
┌──────────────────────────────────────────────────────────────┐
│ 🎸 TourScout                              [Compare] [GitHub]  │
│   Find where your fans are. Plan the tour. Pitch the sponsors.│
│                                                              │
│  Artist  [ Hovvdy                         ]  or "sounds like" │
│  Region  [ US Midwest ▾ ]   Window [ Apr 3 – Apr 20 ]         │
│  Shows   [ 10 ]   Typical draw [ 300–600 ]   Home [ Austin ]  │
│  Past cities / streams  [ + add cities ] [ ⬆ CSV ] [📷 screenshot]│
│                                              [ Scout my tour → ]│
│  Try:  [Men I Trust] [Hovvdy] [Prateek Kuhad] [Easy Wanderlings*] │
│        *not on Qloo → "sounds like" demo                      │
└──────────────────────────────────────────────────────────────┘
```

## 2. Confirm artist (checkpoint 1)
```
┌───────────────────────────────┬──────────────────────────────┐
│ Is this you?                  │ Agent timeline (live)         │
│ ● Hovvdy · indie pop · pop .90│ ✓ parsed intake               │
│ ○ someone else                │ ✓ resolve_artist "Hovvdy"     │
│ Add "sounds like" signals:    │ ⏸ waiting for you             │
│ [Pinegrove ✕] [+ add]         │                               │
│               [ Yes, continue → ]                             │
└───────────────────────────────┴──────────────────────────────┘
```

## 3. Demand map (checkpoint 2)
```
┌──────────────────────────────────────────────────────────────┐
│  🗺  heatmap layer        ● unserved   ● proven   ○ low        │
│     ●Minneapolis   ●Madison  ●Milwaukee                       │
│          ●Des Moines     ●Chicago(proven)                     │
│   ●Omaha        ●Lawrence      ●Columbus(unserved!)           │
├──────────────────────────────────────────────────────────────┤
│ City         Demand  Your reach  Gap   Label        Include   │
│ Columbus       82       12       +70   UNSERVED      [✓]      │
│ Madison        79       20       +59   UNSERVED      [✓]      │
│ Chicago        91       85        +6   PROVEN        [✓]      │
│ Omaha          41        5       +36   low           [ ]      │
│                                        [ Build route → ]      │
└──────────────────────────────────────────────────────────────┘
```

## 4. Tour plan
```
┌──────────────────────────────┬───────────────────────────────┐
│ Apr 3  Chicago     (proven)  │    🗺  route line + pins       │
│ Apr 4  Milwaukee   145 km    │                               │
│ Apr 5  — day off —           │                               │
│ Apr 6  Madison     125 km    │                               │
│ …                            │                               │
│ [Export CSV] [Export ICS]    │                               │
├──────────────────────────────┴───────────────────────────────┤
│ Madison: city card                                            │
│ Venues   High Noon Saloon  aff .91 ★4.6  cap: verify  [why]   │
│ Openers  <local act> 🏠local  pop .71  [DM ✉]                 │
│ Sponsors Polaroid  ▓▓▓▓▓ aff .95 (+8% vs national) [Pitch ✉]  │
│ Promo    <record store>  aff .89                              │
└──────────────────────────────────────────────────────────────┘
```
`[why]` → "Fans of Hovvdy in Madison over-index on this venue (affinity 0.91). Rated 4.6. Live-music venue tag."

## 5. Compare
```
┌─────────────────────────────┬────────────────────────────────┐
│ LLM only                    │ TourScout (Qloo-grounded)       │
│ Cities: NYC, LA, Chicago…   │ Columbus, Madison, Chicago…     │
│ Opener: Phoebe Bridgers ⚠   │ Opener: <local act> 🏠 ✓        │
│   bigger than you, not local│   smaller than you, local       │
│ Venue "The Blue Note" ⚠ ?   │ ✓ all venues verified           │
│ Local openers: 1/10         │ Local openers: 8/10             │
└─────────────────────────────┴────────────────────────────────┘
```
