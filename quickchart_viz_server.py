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
OUTPUT_DIR = os.environ.get("QUICKCHART_OUTPUT_DIR", "/app/output/quickchart")
FALLBACK_OUTPUT_DIR = os.environ.get("QUICKCHART_FALLBACK_OUTPUT_DIR", "/tmp/quickchart")
DEFAULT_INCLUDE_BASE64 = os.environ.get("QUICKCHART_INCLUDE_BASE64", "false").strip().lower() == "true"


def _ensure_output_dir() -> str:
    for path in (OUTPUT_DIR, FALLBACK_OUTPUT_DIR):
        try:
            os.makedirs(path, exist_ok=True)
            return path
        except Exception as exc:
            logger.error("Failed to ensure output directory %s: %s", path, exc)
    return FALLBACK_OUTPUT_DIR


def _generate_filename(prefix: str, extension: str) -> str:
    safe_prefix = prefix.replace(" ", "_").replace("/", "_").replace("\\", "_").lower()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if extension.startswith("."):
        extension = extension[1:]
    return f"{safe_prefix}_{stamp}.{extension or 'png'}"


def _relative_download_path(path: str, root: str | None = None) -> str | None:
    try:
        base = os.path.abspath(root or OUTPUT_DIR)
        target = os.path.abspath(path)
        if not target.startswith(base):
            return None
        rel = os.path.relpath(target, base).replace("\\", "/")
        return f"/files/{rel}"
    except Exception:
        return None


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


def _format_binary_response(
    content: bytes,
    mime: str,
    summary: str,
    prefix: str,
    save_as: str = "",
    include_base64: str = "",
) -> str:
    if not content:
        return f"⚠️ Warning: QuickChart returned an empty payload.\nSummary: {summary} | Generated at {_iso_timestamp()}"

    directory = _ensure_output_dir()
    filename = save_as.strip() or _generate_filename(prefix, mime.split("/")[-1])
    path = os.path.join(directory, filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(content)

    hint = _relative_download_path(path, directory) or "(serve file manually)"

    include = include_base64.strip().lower()
    include_flag = DEFAULT_INCLUDE_BASE64
    if include in {"true", "false"}:
        include_flag = include == "true"

    base64_block = "(base64 omitted; set include_base64=true to embed)"
    if include_flag:
        base64_block = base64.b64encode(content).decode("ascii")

    return f"""✅ Success:
- File saved: {path}
- Download URL: {hint}
- MIME type: {mime}
- Base64 payload:
{base64_block}

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
async def render_chart(
    config: str = "",
    width: str = "",
    height: str = "",
    format: str = "png",
    background: str = "",
    save_as: str = "",
    include_base64: str = "",
) -> str:
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
    return _format_binary_response(
        response.content,
        mime,
        "Chart rendered via QuickChart.",
        prefix="chart",
        save_as=save_as,
        include_base64=include_base64,
    )


@mcp.tool()
async def render_graphviz(
    graph: str = "",
    layout: str = "",
    format: str = "png",
    save_as: str = "",
    include_base64: str = "",
) -> str:
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
    return _format_binary_response(
        response.content,
        mime,
        "Graphviz diagram rendered via QuickChart.",
        prefix="graphviz",
        save_as=save_as,
        include_base64=include_base64,
    )


@mcp.tool()
async def render_mermaid(
    mermaid: str = "",
    theme: str = "",
    format: str = "png",
    save_as: str = "",
    include_base64: str = "",
) -> str:
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
    return _format_binary_response(
        response.content,
        mime,
        "Mermaid diagram rendered via QuickChart.",
        prefix="mermaid",
        save_as=save_as,
        include_base64=include_base64,
    )


@mcp.tool()
async def render_qrcode(
    text: str = "",
    size: str = "",
    correction: str = "",
    save_as: str = "",
    include_base64: str = "",
) -> str:
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
    return _format_binary_response(
        response.content,
        "image/png",
        "QR code generated via QuickChart.",
        prefix="qrcode",
        save_as=save_as,
        include_base64=include_base64,
    )


@mcp.tool()
async def render_wordcloud(
    words: str = "",
    format: str = "png",
    width: str = "",
    height: str = "",
    save_as: str = "",
    include_base64: str = "",
) -> str:
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
    return _format_binary_response(
        response.content,
        mime,
        "Word cloud generated via QuickChart.",
        prefix="wordcloud",
        save_as=save_as,
        include_base64=include_base64,
    )


if __name__ == "__main__":
    logger.info("Starting QuickChart Viz MCP server...")
    try:
        mcp.run(transport="stdio")
    except Exception as exc:
        logger.error("Server error: %s", exc, exc_info=True)
        sys.exit(1)
