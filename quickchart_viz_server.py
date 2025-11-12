#!/usr/bin/env python3
"""Simple QuickChart Viz MCP Server - Render charts and graphics via QuickChart."""

import os
import sys
import json
import logging
import base64
from datetime import datetime, timezone

import httpx
from mcp.server.fastmcp import FastMCP


LOG_LEVEL = os.environ.get("MCP_LOG_LEVEL", "WARNING").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.WARNING),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("quickchart_viz-server")

mcp = FastMCP("quickchart_viz", stateless_http=True)

QUICKCHART_BASE_URL = os.environ.get("QUICKCHART_BASE_URL", "https://quickchart.io").rstrip("/")
QUICKCHART_API_KEY = os.environ.get("QUICKCHART_API_KEY", "").strip()
DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("QUICKCHART_TIMEOUT_SECONDS", "20"))


def _iso_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if QUICKCHART_API_KEY:
        headers["X-QuickChart-Api-Key"] = QUICKCHART_API_KEY
    return headers


def _load_json(raw: str, label: str):
    if not raw.strip():
        return False, f"❌ Error: {label} is required."
    try:
        data = json.loads(raw)
        return True, data
    except json.JSONDecodeError as exc:
        return False, f"❌ Error: Invalid {label} JSON ({exc})."


def _encode_payload(content: bytes, mime: str, summary: str) -> str:
    if not content:
        return f"⚠️ Warning: QuickChart returned an empty payload.\nSummary: {summary} | Generated at {_iso_timestamp()}"
    encoded = base64.b64encode(content).decode("ascii")
    return f"""✅ Success:
- MIME type: {mime}
- Base64 payload:
{encoded}

Summary: {summary} | Generated at {_iso_timestamp()}"""


async def _post(path: str, payload: dict, expected: str) -> tuple:
    url = f"{QUICKCHART_BASE_URL}{path}"
    timeout = httpx.Timeout(DEFAULT_TIMEOUT_SECONDS)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=_headers(), json=payload)
            response.raise_for_status()
            return True, response
    except httpx.HTTPStatusError as exc:
        logger.error("QuickChart %s call failed with status %s", expected, exc.response.status_code)
        return False, f"❌ API Error: {exc.response.status_code} while generating {expected}."
    except Exception as exc:
        logger.error("QuickChart %s call failed: %s", expected, exc)
        return False, f"❌ Error: {str(exc)}"


async def _get(path: str, params: dict, expected: str) -> tuple:
    url = f"{QUICKCHART_BASE_URL}{path}"
    timeout = httpx.Timeout(DEFAULT_TIMEOUT_SECONDS)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return True, response
    except httpx.HTTPStatusError as exc:
        logger.error("QuickChart %s call failed with status %s", expected, exc.response.status_code)
        return False, f"❌ API Error: {exc.response.status_code} while generating {expected}."
    except Exception as exc:
        logger.error("QuickChart %s call failed: %s", expected, exc)
        return False, f"❌ Error: {str(exc)}"


def _validate_dimension(value: str, label: str) -> tuple:
    if not value.strip():
        return True, None
    try:
        parsed = int(value.strip())
        if parsed <= 0:
            return False, f"❌ Error: {label} must be positive."
        return True, parsed
    except ValueError:
        return False, f"❌ Error: {label} must be an integer."


@mcp.tool()
async def render_chart(config: str = "", width: str = "", height: str = "", format: str = "png", background: str = "") -> str:
    """Render a QuickChart chart from a Chart.js config."""
    ok, parsed_config = _load_json(config, "config")
    if not ok:
        return parsed_config

    ok_w, parsed_width = _validate_dimension(width, "width")
    if not ok_w:
        return parsed_width
    ok_h, parsed_height = _validate_dimension(height, "height")
    if not ok_h:
        return parsed_height

    body = {"chart": parsed_config}
    if parsed_width:
        body["width"] = parsed_width
    if parsed_height:
        body["height"] = parsed_height
    if background.strip():
        body["backgroundColor"] = background.strip()
    fmt = format.strip().lower() or "png"
    body["format"] = fmt

    success, response = await _post("/chart", body, "chart")
    if not success:
        return response

    mime = f"image/{fmt}" if fmt in {"png", "jpeg", "jpg", "webp"} else "application/octet-stream"
    return _encode_payload(response.content, mime, "Chart rendered via QuickChart.")


@mcp.tool()
async def render_graphviz(graph: str = "", layout: str = "", format: str = "png") -> str:
    """Render a Graphviz diagram via QuickChart."""
    if not graph.strip():
        return "❌ Error: graph definition is required."
    body = {"graph": graph}
    if layout.strip():
        body["layout"] = layout.strip()
    fmt = format.strip().lower() or "png"
    body["format"] = fmt

    success, response = await _post("/graphviz", body, "graphviz")
    if not success:
        return response
    mime = f"image/{fmt}" if fmt in {"png", "jpeg", "jpg", "svg"} else "application/octet-stream"
    return _encode_payload(response.content, mime, "Graphviz diagram rendered via QuickChart.")


@mcp.tool()
async def render_mermaid(mermaid: str = "", theme: str = "", format: str = "png") -> str:
    """Render a Mermaid diagram via QuickChart."""
    if not mermaid.strip():
        return "❌ Error: mermaid definition is required."
    body = {"chart": mermaid}
    if theme.strip():
        body["theme"] = theme.strip()
    fmt = format.strip().lower() or "png"
    body["format"] = fmt

    success, response = await _post("/mermaid", body, "mermaid")
    if not success:
        return response
    mime = f"image/{fmt}" if fmt in {"png", "svg"} else "application/octet-stream"
    return _encode_payload(response.content, mime, "Mermaid diagram rendered via QuickChart.")


@mcp.tool()
async def render_qrcode(text: str = "", size: str = "", correction: str = "") -> str:
    """Generate a QR code image via QuickChart."""
    if not text.strip():
        return "❌ Error: text is required."
    params = {"text": text.strip()}
    if size.strip():
        ok, parsed_size = _validate_dimension(size, "size")
        if not ok:
            return parsed_size
        params["size"] = parsed_size
    if correction.strip():
        params["ecLevel"] = correction.strip().upper()

    success, response = await _get("/qr", params, "QR code")
    if not success:
        return response
    return _encode_payload(response.content, "image/png", "QR code generated via QuickChart.")


@mcp.tool()
async def render_wordcloud(words: str = "", format: str = "png", width: str = "", height: str = "") -> str:
    """Generate a word cloud via QuickChart."""
    if not words.strip():
        return "❌ Error: words JSON is required."
    ok_words, parsed_words = _load_json(words, "words")
    if not ok_words:
        return parsed_words

    body = {"weights": parsed_words}
    fmt = format.strip().lower() or "png"
    body["format"] = fmt

    ok_w, parsed_width = _validate_dimension(width, "width")
    if not ok_w:
        return parsed_width
    ok_h, parsed_height = _validate_dimension(height, "height")
    if not ok_h:
        return parsed_height
    if parsed_width:
        body["width"] = parsed_width
    if parsed_height:
        body["height"] = parsed_height

    success, response = await _post("/wordcloud", body, "word cloud")
    if not success:
        return response
    mime = f"image/{fmt}" if fmt in {"png", "jpeg", "jpg"} else "application/octet-stream"
    return _encode_payload(response.content, mime, "Word cloud generated via QuickChart.")


if __name__ == "__main__":
    logger.info("Starting QuickChart Viz MCP server...")
    try:
        mcp.run(transport="stdio")
    except Exception as exc:
        logger.error("Server error: %s", exc, exc_info=True)
        sys.exit(1)
