"""
HTML → Elementor JSON converter (deterministic parser).
Shared module used by all Vercel API functions.
Based on SKILL-html-to-elementor.md v1.1
"""

import re
import uuid
import json
import hashlib
import logging

from bs4 import BeautifulSoup, NavigableString, Tag

try:
    import cssutils
    cssutils.log.setLevel(logging.CRITICAL)
    CSSUTILS_AVAILABLE = True
except ImportError:
    CSSUTILS_AVAILABLE = False


def make_id(seed: str = "") -> str:
    raw = seed if seed else str(uuid.uuid4())
    return hashlib.md5(raw.encode()).hexdigest()[:8]


def css_size(val: str) -> dict:
    m = re.match(r"([\d.]+)(px|em|rem|%|vw|vh)", val)
    return {"unit": m.group(2), "size": float(m.group(1))} if m else {"unit": "px", "size": 16}


def css_shorthand_to_elementor(prop: str, val: str) -> dict:
    parts = val.split()
    top = right = bottom = left = "0px"
    if len(parts) == 1:
        top = right = bottom = left = parts[0]
    if len(parts) == 2:
        top = bottom = parts[0]; right = left = parts[1]
    if len(parts) == 3:
        top = parts[0]; right = left = parts[1]; bottom = parts[2]
    if len(parts) == 4:
        top, right, bottom, left = parts

    def sz(v):
        m = re.match(r"([\d.]+)", v)
        return float(m.group(1)) if m else 0

    return {
        f"{prop}_top":    {"unit": "px", "size": sz(top)},
        f"{prop}_right":  {"unit": "px", "size": sz(right)},
        f"{prop}_bottom": {"unit": "px", "size": sz(bottom)},
        f"{prop}_left":   {"unit": "px", "size": sz(left)},
    }


def parse_inline_style(style_str: str) -> dict:
    out = {}
    if not style_str:
        return out
    if CSSUTILS_AVAILABLE:
        sheet = cssutils.parseStyle(style_str)
        for prop in sheet:
            p, v = prop.name, prop.value
            if p == "color":              out["color"] = v
            if p == "background-color":   out["background_color"] = v
            if p == "font-size":          out["typography_font_size"] = css_size(v)
            if p == "font-weight":        out["typography_font_weight"] = v
            if p == "text-align":         out["align"] = v
            if p == "padding":            out.update(css_shorthand_to_elementor("padding", v))
            if p == "margin":             out.update(css_shorthand_to_elementor("margin", v))
    else:
        for decl in style_str.split(";"):
            decl = decl.strip()
            if ":" not in decl:
                continue
            p, _, v = decl.partition(":")
            p, v = p.strip(), v.strip()
            if p == "color":            out["color"] = v
            if p == "background-color": out["background_color"] = v
            if p == "text-align":       out["align"] = v
    return out


def css_text_align(tag) -> str:
    style = tag.get("style", "")
    m = re.search(r"text-align\s*:\s*(\w+)", style)
    return m.group(1) if m else "left"


CSS_COMPLEX_SIGNALS = [
    r"@keyframes", r"display\s*:\s*grid", r"--[\w-]+\s*:",
    r"clip-path\s*:", r"@media.*\(max-width", r"::before|::after", r"animation\s*:",
]
JS_COMPLEX_SIGNALS = [
    r"addEventListener", r"querySelector", r"IntersectionObserver",
    r"fetch\(", r"new\s+\w+\(", r"gsap\.", r"Swiper\(",
]


def is_complex(tag) -> bool:
    if not isinstance(tag, Tag):
        return False
    styles  = " ".join(s.string or "" for s in tag.find_all("style"))
    scripts = " ".join(s.string or "" for s in tag.find_all("script"))
    inline  = tag.get("style", "")
    combined = styles + scripts + inline
    for pattern in CSS_COMPLEX_SIGNALS + JS_COMPLEX_SIGNALS:
        if re.search(pattern, combined):
            return True
    return False


def _widget(id_seed, widget_type, settings):
    return {"id": make_id(id_seed), "elType": "widget", "widgetType": widget_type,
            "settings": settings, "elements": [], "isInner": False}


def html_snippet_widget(tag) -> dict:
    raw = str(tag)
    return _widget(raw[:40], "html", {"html": raw})


def text_editor_widget(html: str) -> dict:
    return _widget(html[:40], "text-editor", {"editor": html})


def image_widget(img_tag, link: str = "") -> dict:
    src = img_tag.get("src", ""); alt = img_tag.get("alt", "")
    settings = {"image": {"url": src, "id": "", "alt": alt, "source": "external"},
                "image_size": "full", "align": "center"}
    if link:
        settings["link_to"] = "custom"
        settings["link"] = {"url": link, "is_external": True, "nofollow": False}
    return _widget(src, "image", settings)


def button_widget(tag) -> dict:
    href = tag.get("href", "#") if tag.name == "a" else "#"
    return _widget(tag.get_text(), "button", {
        "text": tag.get_text(strip=True),
        "link": {"url": href, "is_external": False, "nofollow": False},
        "align": "center", "button_type": "default",
    })


def icon_list_widget(ul_tag) -> dict:
    items = [{"id": make_id(li.get_text()), "text": li.get_text(strip=True),
              "icon": {"value": "fas fa-circle", "library": "fa-solid"}, "link": {"url": ""}}
             for li in ul_tag.find_all("li", recursive=False)]
    return _widget(str(ul_tag)[:30], "icon-list", {"icon_list": items})


def youtube_url(tag) -> str | None:
    src = tag.get("src", "") + tag.get("data-src", "")
    m = re.search(r"(youtube\.com|youtu\.be)/(?:embed/|watch\?v=)?([A-Za-z0-9_-]{11})", src)
    return f"https://www.youtube.com/watch?v={m.group(2)}" if m else None


def video_widget(tag) -> dict:
    yt = youtube_url(tag)
    settings = {"video_type": "youtube", "youtube_url": yt} if yt else \
               {"video_type": "hosted", "hosted_url": {"url": tag.get("src", "")}}
    return _widget(str(settings), "video", settings)


def divider_widget(tag) -> dict:
    return _widget("divider", "divider", {"style": "solid", "weight": {"unit": "px", "size": 1}})


def node_to_widget(tag) -> dict | None:
    if not isinstance(tag, Tag):
        return None
    name = tag.name
    text = tag.get_text(strip=True)

    if name in ("h1","h2","h3","h4","h5","h6"):
        settings = {"title": text, "header_size": name, "align": css_text_align(tag)}
        settings.update(parse_inline_style(tag.get("style", "")))
        return {"id": make_id(str(tag)), "elType": "widget", "widgetType": "heading",
                "settings": settings, "elements": [], "isInner": False}

    if name == "p":               return text_editor_widget(str(tag))
    if name == "img":             return image_widget(tag)
    if name in ("ul","ol"):       return icon_list_widget(tag)
    if name == "a" and tag.find("img"):
        return image_widget(tag.find("img"), link=tag.get("href", ""))
    if name == "button" or "btn" in tag.get("class", []):
        return button_widget(tag)
    if name == "video" or (name == "iframe" and youtube_url(tag)):
        return video_widget(tag)
    if name == "iframe":          return _widget(str(tag)[:40], "html", {"html": str(tag)})
    if name == "hr":              return divider_widget(tag)
    if name == "blockquote":      return text_editor_widget(str(tag))
    if name == "table":           return _widget(str(tag)[:40], "html", {"html": str(tag)})

    inner_html = tag.decode_contents()
    if inner_html.strip():
        return text_editor_widget(inner_html)
    return None


def bootstrap_col_to_elementor(classes: list) -> int:
    for cls in classes:
        if cls.startswith("col-md-") or cls.startswith("col-lg-"):
            return round((int(cls.split("-")[-1]) / 12) * 100)
    return 100


def make_column(widgets: list, width_pct: int = 100) -> dict:
    return {"id": make_id(), "elType": "column", "isInner": False,
            "settings": {"_column_size": width_pct, "_inline_size": None}, "elements": widgets}


def make_section(columns: list, bg_color: str = "", bg_image: str = "") -> dict:
    settings: dict = {"layout": "boxed", "gap": "default",
                      "content_width": {"unit": "px", "size": 1140}}
    if bg_color:
        settings["background_background"] = "classic"
        settings["background_color"] = bg_color
    if bg_image:
        settings["background_background"] = "classic"
        settings["background_image"] = {"url": bg_image, "id": ""}
        settings["background_size"] = "cover"
    return {"id": make_id(), "elType": "section", "isInner": False,
            "settings": settings, "elements": columns}


def is_row_container(tag) -> bool:
    if not isinstance(tag, Tag):
        return False
    classes = tag.get("class", [])
    style   = tag.get("style", "")
    return ("row" in classes or "flex" in style or "grid" in style or
            any(c.startswith("col-") for child in tag.find_all(True, recursive=False)
                for c in child.get("class", [])))


def get_column_children(tag) -> list:
    return [c for c in tag.find_all(True, recursive=False)
            if isinstance(c, Tag) and c.name in ("div","article","aside","section","li")]


def html_to_elementor(raw_html: str) -> list:
    soup = BeautifulSoup(raw_html, "lxml")
    for tag in soup(["noscript", "meta", "link", "head"]):
        tag.decompose()

    body = soup.find("body") or soup
    sections = []

    for child in body.children:
        if not isinstance(child, Tag) or not child.name:
            continue

        if is_complex(child):
            col = make_column([html_snippet_widget(child)], 100)
            sections.append(make_section([col]))
            continue

        if is_row_container(child):
            col_tags = get_column_children(child)
            if col_tags:
                columns = []
                for col_tag in col_tags:
                    width = bootstrap_col_to_elementor(col_tag.get("class", []))
                    widgets = [
                        w for c in col_tag.children
                        if isinstance(c, Tag) and c.name
                        for w in [html_snippet_widget(c) if is_complex(c) else node_to_widget(c)]
                        if w
                    ]
                    if widgets:
                        columns.append(make_column(widgets, width))
                if columns:
                    sections.append(make_section(columns))
                continue

        widget = node_to_widget(child)
        if widget:
            style_settings = parse_inline_style(child.get("style", ""))
            bg_color = style_settings.get("background_color", "")
            sections.append(make_section([make_column([widget], 100)], bg_color=bg_color))

    return sections
