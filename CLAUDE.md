# QuickChart Viz MCP Server Notes

## Overview
- **Service name:** QuickChart Viz
- **Server entrypoint:** `quickchart_viz_server.py`
- **Purpose:** Render charts, diagrams, QR codes, and word clouds through QuickChart.

## Configuration
- Env vars:
  - `QUICKCHART_BASE_URL` (default `https://quickchart.io`)
  - `QUICKCHART_API_KEY` (optional, adds `X-QuickChart-Api-Key` header)
  - `QUICKCHART_TIMEOUT_SECONDS` (default `20`)
- No filesystem outputs; responses embed base64 image payloads.

## Tools
- `render_chart(config="", width="", height="", format="png", background="")`
  - Parses Chart.js JSON, optional size/background, calls `/chart`.
- `render_graphviz(graph="", layout="", format="png")`
  - Accepts DOT syntax, optional layout, calls `/graphviz`.
- `render_mermaid(mermaid="", theme="", format="png")`
  - Mermaid syntax, optional theme, calls `/mermaid`.
- `render_qrcode(text="", size="", correction="")`
  - Quick QR generation via `/qr` with optional size and error correction.
- `render_wordcloud(words="", format="png", width="", height="")`
  - Weighted words JSON, optional dimensions, calls `/wordcloud`.

## Error Handling
- Validates JSON inputs and numeric parameters.
- Converts HTTP and network exceptions into friendly ❌ messages.

## Logging
- INFO-level logging to stderr via `logging.basicConfig`.
- Logs API failures with status codes.

## Docker Runtime
- Based on `python:3.11-slim`.
- Dependencies: `mcp[cli]`, `httpx`.
- Runs as non-root `mcpuser`.

## Testing Tips
```bash
export QUICKCHART_API_KEY="your-key"
python quickchart_viz_server.py
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python quickchart_viz_server.py
```

## Maintenance
- Keep docstrings one line.
- When adding tools, reuse `_post`, `_get`, `_encode_payload`.
- Ensure new endpoints embed base64 outputs for portability.
