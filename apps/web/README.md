# tourscout-web

The TourScout web app: React 19 + Vite + Tailwind 4 + Leaflet. It talks to the API in `apps/api` (see `docs/api.md`).

## Run
```bash
# terminal 1: the API
cd apps/api && uv run tourscout-api          # http://127.0.0.1:8000

# terminal 2: the web app
cd apps/web && npm install && npm run dev     # http://localhost:5173
```
`VITE_API_URL` (see `.env.example`) points the app at another API, e.g. the hosted one. The API must list the web origin in
`WEB_ORIGINS`.

## What's on screen
| Piece | File |
|---|---|
| Request form, demo artists, CSV/screenshot upload | `src/components/StartPanel.tsx` |
| Live agent steps (streamed) | `src/components/Trace.tsx` |
| "Is this you?" and "Pick your cities" checkpoints | `src/components/Checkpoints.tsx` |
| Demand map + numbered route | `src/components/TourMap.tsx` |
| The plan as a tour poster | `src/components/TourPoster.tsx` |
| Venue, openers (with hometown badge), brands, poster spots, opener DM | `src/components/CityCard.tsx` |
| Compare with the LLM-only plan, outreach drafts | `src/components/Extras.tsx` |
| Run state machine (start → checkpoints → plan → refine) | `src/useTour.ts` |
| API client + SSE parser | `src/api.ts` |

## Design
Riso inks on cool paper: ink blue `#22306E`, riso pink `#E6457A` for unserved demand and actions, yellow `#F5C344` as a
highlight. Bricolage Grotesque (condensed) for the poster, Instrument Sans for everything else. The plan reads like a
gig poster's date list; everything around it stays quiet. Keyboard focus is visible and motion respects
`prefers-reduced-motion`. Map tiles: Esri light-gray canvas (no key needed).

## Test
```bash
npm test          # SSE parser, wording, poster rendering
npm run build     # type-check + production build
```
