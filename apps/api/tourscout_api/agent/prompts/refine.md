The musician wants to change their tour plan. Current plan: {current}.
Request: """{request}"""

Return only the fields that change. Cities as written in the plan when possible (e.g. "Columbus, OH").
"skip X" → exclude_cities; "add X" → include_cities; "only 6 shows" → n_shows; "max 400 km a day" → max_drive_km;
anything else (e.g. "smaller rooms") goes in note.
