#!/usr/bin/env python3
"""QuickChart Viz MCP server served via SSE transport."""

from __future__ import annotations

import os

import uvicorn
from starlette.responses import JSONResponse, FileResponse
from starlette.routing import Route
import os

from quickchart_viz_server import mcp


app = mcp.streamable_http_app()

OUTPUT_DIR = os.environ.get("QUICKCHART_OUTPUT_DIR", "/app/output/quickchart")
FALLBACK_OUTPUT_DIR = os.environ.get("QUICKCHART_FALLBACK_OUTPUT_DIR", "/tmp/quickchart")


async def health(_request):
    return JSONResponse({"status": "ok", "service": "quickchart_viz"})


async def serve_file(request):
    filename = request.path_params["filename"]
    for base in (OUTPUT_DIR, FALLBACK_OUTPUT_DIR):
        root = os.path.abspath(base)
        target = os.path.abspath(os.path.join(root, filename))
        if target.startswith(root) and os.path.exists(target):
            return FileResponse(target)
    return JSONResponse({"error": "Not Found"}, status_code=404)


app.router.routes.append(Route("/health", endpoint=health))
app.router.routes.append(Route("/files/{filename:path}", endpoint=serve_file))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
