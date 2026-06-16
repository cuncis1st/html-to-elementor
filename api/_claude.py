"""
Claude API fallback — shared module for Vercel serverless functions.
"""

import os
import re
import json
import httpx

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = """You are an Elementor JSON generator.
Given raw HTML, return ONLY a valid JSON array (no markdown, no preamble)
that Elementor stores as _elementor_data.

ROUTING RULE (apply first, before any other mapping):
If ANY element contains @keyframes, display:grid with grid-template, CSS custom
properties (--var), clip-path, addEventListener, querySelector,
IntersectionObserver, fetch(), or third-party lib calls (Swiper, gsap, Chart.js)
→ output that element as widgetType "html" with its FULL outer HTML (including
  nested <style> and <script> tags) in the "html" settings key.
  Do NOT decompose complex components into sub-widgets.

For all other elements:
- Wrap content in sections → columns → widgets.
- heading (h1-h6)     → widgetType "heading"
- paragraph / text    → widgetType "text-editor"
- image               → widgetType "image"
- button / link-btn   → widgetType "button"
- ul / ol             → widgetType "icon-list"
- hr                  → widgetType "divider"
- YouTube iframe      → widgetType "video"
- tables, plain forms → widgetType "html"
- Every node needs: id (8-char hex), elType, settings, elements, isInner (false).
- Preserve simple inline styles as Elementor responsive settings.
Output ONLY the JSON array. No explanation. No markdown fences."""


async def convert_with_claude(raw_html: str) -> list:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    model   = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")

    if not api_key or api_key.startswith("sk-ant-xxx"):
        raise RuntimeError("ANTHROPIC_API_KEY is not configured in Vercel Environment Variables.")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 8192,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": f"Convert this HTML to Elementor JSON:\n\n{raw_html}"}],
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(ANTHROPIC_API_URL, headers=headers, json=payload)

    if response.status_code != 200:
        raise RuntimeError(f"Claude API error {response.status_code}: {response.text[:400]}")

    text = response.json()["content"][0]["text"].strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)

    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Claude returned invalid JSON: {exc}")

    if not isinstance(result, list):
        raise RuntimeError("Claude response is not a JSON array.")

    return result
