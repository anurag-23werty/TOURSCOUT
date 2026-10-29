Write the tour brief for {artist}{signal_note}.

FACTS (the only data you may use):
{facts}

Instructions:
- One stop per metro in the route (the dates and order are fixed by the route; you don't need to change them).
- For each stop pick venue_id from that metro's venues, 1–2 opener_ids from its openers (prefer badge "based_here"),
  0–2 sponsor_ids and up to 3 promo_ids, all BY ID from that metro's candidates. If a metro has no venues, use
  venue_id "" and say "venue to find" in why.
- "why": one or two sentences explaining the city and picks with the given numbers, e.g. "demand 82 but your reach is 12:
  fans you aren't reaching yet". Venue capacity is unknown: say "check capacity" instead of guessing.
- headline: one line. summary: 2–3 sentences about the shape of the tour (unserved vs proven cities, total km).
- sponsor_strategy: which brands to approach and why, from the sponsor data (uplift, new_in_city).
- risks: missing data or long drives, from the facts.
- Use only numbers that appear in FACTS.
{feedback}
