# QuickChart Viz MCP Server

A Model Context Protocol (MCP) server that renders charts and graphics using the QuickChart API.

## Purpose

This MCP server provides a secure interface for AI assistants to generate Chart.js figures, Graphviz and Mermaid diagrams, QR codes, and word clouds powered by QuickChart.

## Features

### Current Implementation

- **`render_chart`** - Renders Chart.js configurations into images with optional sizing and background.
- **`render_graphviz`** - Produces Graphviz diagrams (DOT syntax) with optional layout selection.
- **`render_mermaid`** - Generates Mermaid diagrams with optional theming.
- **`render_qrcode`** - Creates QR codes with adjustable size and error correction levels.
- **`render_wordcloud`** - Builds word clouds from weighted word JSON payloads.

## Prerequisites

- Docker Desktop with MCP Toolkit enabled
- Docker MCP CLI plugin (`docker mcp`)
- (Optional) QuickChart API key for higher limits (`QUICKCHART_API_KEY`)

## Installation

See the step-by-step instructions provided with the files.

## Usage Examples

In Claude Desktop, you can ask:

- "Render a QuickChart bar chart with this Chart.js config and width 600."
- "Generate a flow diagram from this Graphviz definition."
- "Create a Mermaid sequence diagram with the dark theme."
- "Build a QR code for this URL with high error correction."
- "Produce a word cloud from these weighted terms."

## Architecture

Claude Desktop → MCP Gateway → QuickChart Viz MCP Server → QuickChart API
↓
Docker Desktop Secrets (optional)
(QUICKCHART_API_KEY)

## Development

### Local Testing

```bash
# Optional: set API key for QuickChart
export QUICKCHART_API_KEY="test-key"

# Run directly
python quickchart_viz_server.py

# Test MCP protocol
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python quickchart_viz_server.py
```

### Adding New Tools

1. Add the function to `quickchart_viz_server.py`
2. Decorate with `@mcp.tool()`
3. Update the catalog entry with the new tool name
4. Rebuild the Docker image

### Troubleshooting

**Tools Not Appearing**
- Verify Docker image built successfully
- Check catalog and registry files
- Ensure Claude Desktop config includes custom catalog
- Restart Claude Desktop

**API Errors**
- Verify QuickChart API is reachable
- Set `QUICKCHART_API_KEY` if rate-limited
- Confirm JSON payloads are valid

### Security Considerations

- Optional API key stored via Docker Desktop secrets
- No sensitive data logged
- Runs as non-root user inside the container

### License

MIT License
