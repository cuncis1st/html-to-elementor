"""
Vercel Python Serverless Function — POST /api/convert/template
Returns Elementor JSON wrapped in the import template envelope.
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from _converter import html_to_elementor
from http.server import BaseHTTPRequestHandler


def count_widgets(nodes: list) -> int:
    total = 0
    for node in nodes:
        if isinstance(node, dict):
            if node.get("elType") == "widget":
                total += 1
            total += count_widgets(node.get("elements", []))
    return total


def cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        for k, v in cors_headers().items():
            self.send_header(k, v)
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._respond(400, {"error": "Invalid JSON body"})
            return

        raw_html = payload.get("html", "").strip()
        use_claude = payload.get("use_claude", False)

        if not raw_html:
            self._respond(400, {"error": "html field must not be empty."})
            return

        method = "deterministic"
        error_msg = None
        sections = []

        try:
            sections = html_to_elementor(raw_html)
        except Exception as exc:
            error_msg = f"Parser error: {exc}"

        if (not sections or use_claude) and os.getenv("USE_CLAUDE_FALLBACK", "false").lower() == "true":
            try:
                import asyncio
                from _claude import convert_with_claude
                sections = asyncio.run(convert_with_claude(raw_html))
                method = "claude"
                error_msg = None
            except Exception as exc:
                error_msg = str(exc)

        template = {
            "version": "0.4",
            "title": "Converted Page",
            "type": "page",
            "content": sections,
        }

        self._respond(200, {
            "success": len(sections) > 0,
            "template": template,
            "template_json": json.dumps(template, ensure_ascii=False, indent=2),
            "widget_count": count_widgets(sections),
            "method": method,
            "error": error_msg,
        })

    def _respond(self, status: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in cors_headers().items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
