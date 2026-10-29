Today is {today}. Turn this request from a musician into the intake fields.

Request:
"""{request}"""

Rules:
- artist: the name exactly as written. sounds_like: only artists the user named as similar.
- regions: what they asked for, e.g. ["Midwest"], ["Texas", "Oklahoma"], ["India"], ["Germany"].
- Dates as YYYY-MM-DD. "next spring" = the next March–May; if no dates are given, leave them null.
- max_drive_km: 0 if they will fly between cities; default 600 if they drive and don't say.
- past_cities: cities they say they played recently. exclude_cities: cities they want to skip.
