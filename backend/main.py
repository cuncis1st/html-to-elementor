"""
FastAPI application — HTML → Elementor JSON Converter
"""

import os
import json
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from converter import html_to_elementor
from claude_fallback import convert_with_claude

load_dotenv()

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="HTML → Elementor JSON Converter",
    description="Converts raw HTML to Elementor _elementor_data JSON",
    version="1.0.0",
)

cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
cors_origins = [o.strip() for o in cors_origins_raw.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ConvertRequest(BaseModel):
    html: str
    use_claude: bool = False


class ConvertResponse(BaseModel):
    success: bool
    data: list
    json_string: str
    widget_count: int
    method: str
    error: str | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "HTML → Elementor JSON Converter API",
        "endpoints": {
            "POST /convert": "Convert HTML to Elementor JSON",
            "GET /health":   "Health check",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/convert", response_model=ConvertResponse)
async def convert(request: ConvertRequest):
    if not request.html.strip():
        raise HTTPException(status_code=400, detail="html field must not be empty.")

    use_fallback = request.use_claude and os.getenv("USE_CLAUDE_FALLBACK", "false").lower() == "true"
    method = "deterministic"
    error_msg = None

    # Always run deterministic parser first
    try:
        sections = html_to_elementor(request.html)
    except Exception as exc:
        sections = []
        error_msg = f"Parser error: {exc}"

    # If deterministic produced nothing AND claude fallback is enabled → use AI
    if (not sections or use_fallback) and os.getenv("USE_CLAUDE_FALLBACK", "false").lower() == "true":
        try:
            sections = await convert_with_claude(request.html)
            method = "claude"
            error_msg = None
        except RuntimeError as exc:
            # Keep whatever the deterministic parser produced; surface the error
            error_msg = str(exc)

    def count_widgets(nodes: list) -> int:
        total = 0
        for node in nodes:
            if isinstance(node, dict):
                if node.get("elType") == "widget":
                    total += 1
                total += count_widgets(node.get("elements", []))
        return total

    json_string = json.dumps(sections, ensure_ascii=False, indent=2)

    return ConvertResponse(
        success=len(sections) > 0,
        data=sections,
        json_string=json_string,
        widget_count=count_widgets(sections),
        method=method,
        error=error_msg,
    )


@app.post("/convert/template", response_model=dict)
async def convert_template(request: ConvertRequest):
    """
    Same as /convert but wraps output in the Elementor template envelope
    ready for import via WP Admin → Templates → Import Templates.
    """
    result = await convert(request)
    template = {
        "version": "0.4",
        "title": "Converted Page",
        "type": "page",
        "content": result.data,
    }
    return {
        "success": result.success,
        "template": template,
        "template_json": json.dumps(template, ensure_ascii=False, indent=2),
        "widget_count": result.widget_count,
        "method": result.method,
        "error": result.error,
    }
