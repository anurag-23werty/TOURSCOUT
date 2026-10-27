# Use the TourScout MCP server from Claude Desktop (or any MCP client)

## 1. One-time setup
```bash
cd ~/Tourscout/packages/tourscout_mcp
uv sync
uv run python ../../data/download_geonames.py
uv run pytest            # 29 unit tests, no network
```
`QLOO_API_KEY` must be in `~/Tourscout/.env`.

## 2. Claude Desktop
Open **Settings → Developer → Edit Config** (macOS file: `~/Library/Application Support/Claude/claude_desktop_config.json`) and add:
```json
{
  "mcpServers": {
    "tourscout": {
      "command": "/Users/<you>/.local/bin/uv",
      "args": ["run", "--directory", "/Users/<you>/Tourscout/packages/tourscout_mcp", "tourscout-mcp"]
    }
  }
}
```
Use the full path to `uv` (`which uv`), because Claude Desktop doesn't load your shell's PATH. Restart Claude Desktop; the
tools icon should list 7 TourScout tools.

**Exit test for Phase 2:** ask
> Where should Hovvdy tour in the Midwest, and who should open in Chicago?

Expected (27 Oct run): `demand_map` → Chicago, Lawrence KS, Detroit, Columbus, Des Moines, Bloomington IN…;
`find_openers` → Knox Fortune and Divino Niño (both "based here", MusicBrainz). Every name in the answer should come from a
tool result.

## 3. Claude Code
```bash
claude mcp add tourscout -- uv run --directory ~/Tourscout/packages/tourscout_mcp tourscout-mcp
```

## 4. MCP Inspector (debug the raw tool calls)
```bash
npx @modelcontextprotocol/inspector uv run --directory ~/Tourscout/packages/tourscout_mcp tourscout-mcp
```

## 5. Over HTTP (what the hosted agent uses in Phase 4)
```bash
uv run tourscout-mcp --http --port 8001   # → http://127.0.0.1:8001/mcp
```

## Troubleshooting
| Symptom | Fix |
|---|---|
| Tools don't appear | full path to `uv` in the config; check `~/Library/Logs/Claude/mcp-server-tourscout.log` |
| `QLOO_API_KEY is missing` | key not in the repo-root `.env` |
| `metro roll-up unavailable` | run `data/download_geonames.py` |
| `find_openers` is slow the first time | MusicBrainz allows 1 request/second; results are cached, or pass `check_local=false` |
| `… is not verified for urn:entity:…` | the allow-list blocked an untested param on purpose (see `allowlist.py`) |
