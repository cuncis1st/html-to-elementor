# SKILL: HTML → Elementor Widget JSON Converter

**Version:** 1.1 — June 2026  
**Scope:** Parse arbitrary HTML and emit valid Elementor page-builder JSON that recreates the layout as native Elementor widgets inside WordPress.

---

## 1. What This Skill Covers

Convert HTML markup (pasted text, uploaded `.html` file, or a URL's source) into the JSON structure Elementor stores in `wp_postmeta` under the key `_elementor_data`. The output can be:

- Pasted directly into **Elementor → Tools → Import / Export → Import JSON**
- Injected via the WordPress REST API or WP-CLI
- Used as seed data for a custom Elementor widget or template

---

## 2. Conceptual Map: HTML → Elementor

### Elementor's Data Model (as of Elementor 3.x / 2026)

```
Page
 └── Section  (elType: "section")
      └── Column  (elType: "column")
           └── Widget  (elType: "widget", widgetType: "<name>")
```

Every node shares this envelope:

```json
{
  "id": "<8-char hex>",
  "elType": "section | column | widget",
  "settings": { ... },
  "elements": [ ... ],
  "isInner": false
}
```

### Core HTML-to-Widget Mapping Table

| HTML pattern | Elementor widgetType | Key settings keys |
|---|---|---|
| `<h1>`–`<h6>` | `heading` | `title`, `header_size` (h1…h6), `align` |
| `<p>`, `<div>` with text | `text-editor` | `editor` (HTML string) |
| `<img>` | `image` | `image` (id+url object), `image_size`, `align` |
| `<a>` wrapping `<img>` | `image` | `link` (url, is_external, nofollow) |
| `<ul>` / `<ol>` | `icon-list` or `text-editor` | `icon_list` array OR `editor` |
| `<button>`, `<a class="btn">` | `button` | `text`, `link`, `align`, `button_type` |
| `<video>` / YouTube embed | `video` | `video_type`, `youtube_url` / `hosted_url` |
| `<iframe>` | `html` | `html` (raw iframe string) |
| `<form>` | `html` (passthrough) | `html` |
| `<hr>` | `divider` | `style`, `weight`, `color` |
| `<blockquote>` | `text-editor` | `editor` |
| `<table>` | `html` | `html` (raw table string) |
| Flexbox / Grid row | `section` (isInner) + columns | column `_column_size` (100-based integer) |
| CSS background image | `section` → `background_image` | `background_image`, `background_size` |
| `<section>`, `<div.row>` | `section` | `layout`, `gap`, `content_width` |
| **Complex CSS** (Grid, keyframes, custom props, `@media` overrides) | `html` snippet widget | `html` (self-contained `<style>` + markup) |
| **JS interactivity** (sliders, counters, modals, custom events) | `html` snippet widget | `html` (self-contained `<script>` + markup) |
| **Mixed complex CSS + JS component** | `html` snippet widget | `html` (full self-contained bundle) |

---

## 3. Algorithm: Step-by-Step

### Step 1 — Ingest & Normalize HTML

```python
from bs4 import BeautifulSoup
soup = BeautifulSoup(raw_html, "html.parser")
body = soup.find("body") or soup  # work on body content only
```

**Do NOT blindly strip `<script>` and `<style>` tags.** Run the complexity classifier (see Step 1b) first:
- **Complex** `<style>` or `<script>` → keep bundled with its markup, route to `html` snippet widget.
- **Simple** (font loads, trivial resets) → strip safely, let Elementor native settings handle styling.
- Always strip: `<noscript>`, `<meta>`, `<link rel="stylesheet">` pointing to external CDN files.

### Step 1b — Complexity Classifier

Before building the tree, check every block element for signals that force it to become an `html` snippet widget.

```python
CSS_COMPLEX_SIGNALS = [
    r"@keyframes",
    r"display\s*:\s*grid",
    r"--[\w-]+\s*:",           # CSS custom properties
    r"clip-path\s*:",
    r"@media.*\(max-width",
    r"::before|::after",
    r"animation\s*:",
]

JS_COMPLEX_SIGNALS = [
    r"addEventListener",
    r"querySelector",
    r"IntersectionObserver",
    r"fetch\(",
    r"new\s+\w+\(",           # class instantiation (Swiper, Chart, etc.)
    r"gsap\.",
    r"Swiper\(",
]

def is_complex(tag) -> bool:
    """Return True if this element needs the html snippet fallback."""
    styles  = " ".join(s.string or "" for s in tag.find_all("style"))
    scripts = " ".join(s.string or "" for s in tag.find_all("script"))
    inline  = tag.get("style", "")
    combined = styles + scripts + inline
    for pattern in CSS_COMPLEX_SIGNALS + JS_COMPLEX_SIGNALS:
        if re.search(pattern, combined):
            return True
    return False
```

If `is_complex(tag)` returns `True`, call `html_snippet_widget(tag)` — do not recurse into sub-elements.

---

### Step 1c — HTML Snippet Widget Builder

```python
def html_snippet_widget(tag) -> dict:
    """
    Bundle the tag's full outer HTML — including any nested <style> and <script>
    blocks — into a single Elementor html widget. Use this for any component
    that contains complex CSS or JS that Elementor cannot express natively.
    """
    raw = str(tag)   # outer HTML, preserves <style> and <script> children
    return {
        "id": make_id(raw[:40]),
        "elType": "widget",
        "widgetType": "html",
        "settings": {"html": raw},
        "elements": []
    }
```

The Elementor `html` widget renders its content verbatim on the front end, making it the
correct container for self-contained interactive components with their own styles and scripts.

---

### Step 2 — Build a Logical Tree

Walk top-level children of `<body>`. Each direct child becomes either:

- A **Section** (if it is a block container: `<section>`, `<div>`, `<header>`, `<footer>`, `<article>`, `<main>`)
- A **widget** wrapped in an auto-generated Section + Column (for bare `<p>`, `<h1>`, `<img>`, etc.)

For block containers, inspect their direct children:
- If children are laid out side-by-side (detected via `display:flex`, `display:grid`, Bootstrap `.col-*` classes, or multiple `<div>` siblings), map each to a **Column**.
- Otherwise, create a single 100 % Column.

### Step 3 — Resolve Column Widths

```python
def bootstrap_col_to_elementor(classes: list[str]) -> int:
    """Return integer 1–100 representing column width."""
    for cls in classes:
        if cls.startswith("col-md-") or cls.startswith("col-lg-"):
            n = int(cls.split("-")[-1])
            return round((n / 12) * 100)
    return 100  # full width fallback
```

For flex/grid layouts without Bootstrap, divide 100 by the number of sibling columns.

### Step 4 — Convert Each Node to a Widget Dict

```python
import uuid, hashlib

def make_id(seed: str = "") -> str:
    """8-char hex id, stable if seed given."""
    raw = seed or str(uuid.uuid4())
    return hashlib.md5(raw.encode()).hexdigest()[:8]

def node_to_widget(tag) -> dict | None:
    name = tag.name
    text = tag.get_text(strip=True)

    if name in ("h1","h2","h3","h4","h5","h6"):
        return {
            "id": make_id(str(tag)),
            "elType": "widget",
            "widgetType": "heading",
            "settings": {
                "title": text,
                "header_size": name,   # "h1" … "h6"
                "align": css_text_align(tag),
            },
            "elements": []
        }

    if name == "p":
        return text_editor_widget(str(tag))

    if name == "img":
        return image_widget(tag)

    if name in ("ul","ol"):
        return icon_list_widget(tag)  # or text_editor_widget

    if name == "a" and tag.find("img"):
        return image_widget(tag.find("img"), link=tag.get("href",""))

    if name in ("button",) or "btn" in tag.get("class",[]):
        return button_widget(tag)

    if name == "video" or youtube_url(tag):
        return video_widget(tag)

    if name == "iframe":
        return html_widget(str(tag))

    if name == "hr":
        return divider_widget(tag)

    # Generic block → text-editor passthrough
    inner_html = tag.decode_contents()
    if inner_html.strip():
        return text_editor_widget(inner_html)

    return None
```

### Step 5 — Assemble the Full JSON

```python
def build_elementor_json(sections: list[dict]) -> list[dict]:
    """Wrap everything in the top-level array Elementor expects."""
    return sections   # already a list of section dicts

import json
output = json.dumps(build_elementor_json(sections), ensure_ascii=False, indent=2)
```

---

## 4. Full Widget Builder Functions

### 4.1 text-editor

```python
def text_editor_widget(html: str) -> dict:
    return {
        "id": make_id(html[:40]),
        "elType": "widget",
        "widgetType": "text-editor",
        "settings": {"editor": html},
        "elements": []
    }
```

### 4.2 image

```python
def image_widget(img_tag, link: str = "") -> dict:
    src = img_tag.get("src","")
    alt = img_tag.get("alt","")
    settings = {
        "image": {"url": src, "id": "", "alt": alt, "source": "external"},
        "image_size": "full",
        "align": "center"
    }
    if link:
        settings["link_to"] = "custom"
        settings["link"] = {"url": link, "is_external": True, "nofollow": False}
    return {"id": make_id(src), "elType": "widget", "widgetType": "image",
            "settings": settings, "elements": []}
```

### 4.3 button

```python
def button_widget(tag) -> dict:
    href = tag.get("href","#") if tag.name == "a" else "#"
    return {
        "id": make_id(tag.get_text()),
        "elType": "widget",
        "widgetType": "button",
        "settings": {
            "text": tag.get_text(strip=True),
            "link": {"url": href, "is_external": False, "nofollow": False},
            "align": "center",
            "button_type": "default"
        },
        "elements": []
    }
```

### 4.4 icon-list

```python
def icon_list_widget(ul_tag) -> dict:
    items = []
    for li in ul_tag.find_all("li", recursive=False):
        items.append({
            "id": make_id(li.get_text()),
            "text": li.get_text(strip=True),
            "icon": {"value": "fas fa-circle", "library": "fa-solid"},
            "link": {"url": ""}
        })
    return {
        "id": make_id(str(ul_tag)[:30]),
        "elType": "widget",
        "widgetType": "icon-list",
        "settings": {"icon_list": items},
        "elements": []
    }
```

### 4.5 video

```python
import re

def youtube_url(tag) -> str | None:
    src = tag.get("src","") + tag.get("data-src","")
    m = re.search(r"(youtube\.com|youtu\.be)/(?:embed/|watch\?v=)?([A-Za-z0-9_-]{11})", src)
    return f"https://www.youtube.com/watch?v={m.group(2)}" if m else None

def video_widget(tag) -> dict:
    yt = youtube_url(tag)
    if yt:
        settings = {"video_type": "youtube", "youtube_url": yt}
    else:
        src = tag.get("src","")
        settings = {"video_type": "hosted", "hosted_url": {"url": src}}
    return {"id": make_id(str(settings)), "elType": "widget", "widgetType": "video",
            "settings": settings, "elements": []}
```

### 4.6 html (passthrough)

```python
def html_widget(raw: str) -> dict:
    return {"id": make_id(raw[:40]), "elType": "widget", "widgetType": "html",
            "settings": {"html": raw}, "elements": []}
```

### 4.7 divider

```python
def divider_widget(tag) -> dict:
    return {"id": make_id(), "elType": "widget", "widgetType": "divider",
            "settings": {"style": "solid", "weight": {"unit":"px","size":1}},
            "elements": []}
```

---

## 5. Section & Column Skeleton

```python
def make_column(widgets: list[dict], width_pct: int = 100) -> dict:
    return {
        "id": make_id(),
        "elType": "column",
        "settings": {"_column_size": width_pct, "_inline_size": None},
        "elements": widgets
    }

def make_section(columns: list[dict], bg_color: str = "", bg_image: str = "") -> dict:
    settings: dict = {"layout": "boxed", "gap": "default", "content_width": {"unit":"px","size":1140}}
    if bg_color:
        settings["background_background"] = "classic"
        settings["background_color"] = bg_color
    if bg_image:
        settings["background_background"] = "classic"
        settings["background_image"] = {"url": bg_image, "id": ""}
        settings["background_size"] = "cover"
    return {
        "id": make_id(),
        "elType": "section",
        "isInner": False,
        "settings": settings,
        "elements": columns
    }
```

---

## 6. Style Extraction

Extract inline styles and translate them to Elementor settings keys:

```python
import cssutils, logging
cssutils.log.setLevel(logging.CRITICAL)

def parse_inline_style(style_str: str) -> dict:
    """Return a partial Elementor settings dict from an inline style string."""
    out = {}
    sheet = cssutils.parseStyle(style_str)
    for prop in sheet:
        p, v = prop.name, prop.value
        if p == "color":          out["color"] = v
        if p == "background-color": out["background_color"] = v
        if p == "font-size":      out["typography_font_size"] = css_size(v)
        if p == "font-weight":    out["typography_font_weight"] = v
        if p == "text-align":     out["align"] = v
        if p == "padding":        out.update(css_shorthand_to_elementor("padding", v))
        if p == "margin":         out.update(css_shorthand_to_elementor("margin", v))
    return out

def css_size(val: str) -> dict:
    """'16px' → {"unit":"px","size":16}"""
    m = re.match(r"([\d.]+)(px|em|rem|%|vw|vh)", val)
    return {"unit": m.group(2), "size": float(m.group(1))} if m else {"unit":"px","size":16}

def css_shorthand_to_elementor(prop: str, val: str) -> dict:
    parts = val.split()
    top = right = bottom = left = "0px"
    if len(parts) == 1:   top = right = bottom = left = parts[0]
    if len(parts) == 2:   top = bottom = parts[0]; right = left = parts[1]
    if len(parts) == 3:   top = parts[0]; right = left = parts[1]; bottom = parts[2]
    if len(parts) == 4:   top, right, bottom, left = parts
    unit = "px"
    def sz(v): m=re.match(r"([\d.]+)",v); return float(m.group(1)) if m else 0
    return {
        f"{prop}_top":    {"unit":unit,"size":sz(top)},
        f"{prop}_right":  {"unit":unit,"size":sz(right)},
        f"{prop}_bottom": {"unit":unit,"size":sz(bottom)},
        f"{prop}_left":   {"unit":unit,"size":sz(left)},
    }
```

---

## 7. Complete Orchestrator

```python
def html_to_elementor(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")
    # Remove noise
    for tag in soup(["script","style","noscript","meta","link","head"]):
        tag.decompose()

    body = soup.find("body") or soup
    sections = []

    for child in body.children:
        if not hasattr(child, "name") or not child.name:
            continue  # skip NavigableString whitespace

        # Detect multi-column row
        if is_row_container(child):
            col_tags = get_column_children(child)
            columns = []
            for col_tag in col_tags:
                width = bootstrap_col_to_elementor(col_tag.get("class",[]))
                widgets = [
                    w for w in (
                        html_snippet_widget(c) if is_complex(c) else node_to_widget(c)
                        for c in col_tag.children
                        if hasattr(c,"name") and c.name
                    ) if w
                ]
                if widgets:
                    columns.append(make_column(widgets, width))
            if columns:
                sections.append(make_section(columns))
        else:
            # Single-column section
            # Route complex CSS/JS components to html snippet widget
            widget = html_snippet_widget(child) if is_complex(child) else node_to_widget(child)
            if widget:
                col = make_column([widget], 100)
                sections.append(make_section([col]))

    return json.dumps(sections, ensure_ascii=False, indent=2)


def is_row_container(tag) -> bool:
    classes = tag.get("class", [])
    style = tag.get("style","")
    return (
        "row" in classes
        or "flex" in style
        or "grid" in style
        or any(c.startswith("col-") for child in tag.find_all(True, recursive=False)
               for c in child.get("class",[]))
    )

def get_column_children(tag):
    return [c for c in tag.find_all(True, recursive=False)
            if hasattr(c,"name") and c.name in ("div","article","aside","section","li")]
```

---

## 8. Web App UI (React Artifact)

Build the converter as a React artifact with this layout:

```
┌─────────────────────────────────────────────────────┐
│  HTML → Elementor JSON Converter                     │
├──────────────────────┬──────────────────────────────┤
│  [Paste HTML]        │  [JSON output]               │
│  <textarea>          │  <pre> / copy button         │
│                      │                              │
├──────────────────────┴──────────────────────────────┤
│  [Convert] btn   Widget map preview  [Download JSON] │
└─────────────────────────────────────────────────────┘
```

The Claude API (`claude-sonnet-4-6`) powers the conversion logic in the browser — pass the raw HTML and instruct the model to return ONLY valid Elementor JSON. Parse `data.content[0].text` and display in the right panel.

### System prompt template for the API call

```
You are an Elementor JSON generator.
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
- Every node needs: id (8-char hex), elType, settings, elements.
- Preserve simple inline styles as Elementor responsive settings.
Output ONLY the JSON array. No explanation. No markdown fences.
```

---

## 9. Importing the Output into WordPress

### Method A — Elementor Template Import (GUI)
1. Save the JSON to a file: `my-template.json`
2. Wrap it in the template envelope:
```json
{
  "version": "0.4",
  "title": "Converted Page",
  "type": "page",
  "content": [ /* your sections array here */ ]
}
```
3. In WP Admin → **Templates → Saved Templates → Import Templates** → upload the file.

### Method B — WP-CLI (fastest for developers)
```bash
wp post meta update <POST_ID> _elementor_data '<json>' --format=json
wp post meta update <POST_ID> _elementor_edit_mode builder
```

### Method C — WordPress REST API
```js
await fetch(`/wp-json/wp/v2/pages/${postId}`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": "Basic " + btoa("user:app-password")
  },
  body: JSON.stringify({
    meta: { _elementor_data: jsonString, _elementor_edit_mode: "builder" }
  })
});
```

---

## 10. Known Limitations & Workarounds (June 2026)

### Decision Tree: Native Widget vs HTML Snippet

```
Does the element contain complex CSS or JS?
        |
        +-- NO  --> Convert to native Elementor widget (heading, image, button...)
        |           Full Elementor UI control, responsive settings, Motion Effects.
        |
        +-- YES --> Route to html snippet widget (widgetType: "html")
                    Bundle <style> + markup + <script> together as one unit.
                    Elementor renders it verbatim on the front end.
```

**Simple CSS** (safe for native widgets): `color`, `background-color`, `padding`, `margin`, `font-size`, `font-weight`, `text-align`, `border-radius`, `box-shadow`, single-level `display:flex`.

**Complex CSS → use html snippet:** `@keyframes`, `display:grid` with `grid-template-*`, CSS custom properties (`--var`), `clip-path`, `::before`/`::after` with significant rules, `@media` blocks scoped inside a component.

**Complex JS → use html snippet:** Any `<script>` with `addEventListener`, `querySelector`, `IntersectionObserver`, third-party lib calls (`Swiper()`, `gsap.to()`, `new Chart()`), `fetch()`, or ES module `import`.

### Remaining Hard Limitations

| Limitation | Workaround |
|---|---|
| Custom fonts not in Google Fonts | Register via Elementor → Custom Fonts; reference in `typography_font_family` |
| Global CSS (`:root` vars, body resets) | Place in Elementor → Site Settings → Custom CSS, not inside any widget |
| Multiple `<script>` blocks sharing scope | Merge into one `<script>` before bundling into the html snippet widget |
| Elementor Pro widgets (Slider, Popup, Flip Box) | Requires Pro license; stub as `html` snippet or map widgetType manually |
| Image `id` field | Leave `""` for external URLs; Elementor renders via `url` regardless |
| Dynamic data (ACF, Pods, JetEngine) | Not expressible in static HTML; wire Elementor dynamic tags manually post-import |
| `<canvas>` / WebGL | Handled automatically by complexity classifier → html snippet |
| SVG with JS interactivity | Same — complexity classifier routes to html snippet |

---

## 11. Dependencies

```
beautifulsoup4>=4.12
cssutils>=2.11
lxml>=5.2           # faster HTML parser for bs4
```

Install:
```bash
pip install beautifulsoup4 cssutils lxml --break-system-packages
```

For the React/browser version, all parsing happens server-side via the Claude API — no extra npm packages needed.

---

## 12. Testing Checklist

- [ ] Single heading → `heading` widget with correct `header_size`
- [ ] `<p>` with bold/italic inline → `text-editor` with preserved HTML
- [ ] `<img src="...">` → `image` widget with correct URL
- [ ] `<a href="..."><img></a>` → `image` with `link` settings
- [ ] Bootstrap `.row > .col-md-6 + .col-md-6` → 2-column section (50 % each)
- [ ] `<ul>` with 3 items → `icon-list` with 3 entries
- [ ] `<button>` → `button` widget
- [ ] YouTube `<iframe>` → `video` widget with YouTube URL
- [ ] `<table>` → `html` widget passthrough
- [ ] Inline `style="background-color:#fff"` on section → `background_color` in section settings
- [ ] Output imports cleanly into Elementor 3.x / WordPress 6.x (June 2026)
- [ ] Element with `@keyframes` → `html` snippet widget (not broken into sub-widgets)
- [ ] Element with `display:grid` and `grid-template-columns` → `html` snippet widget
- [ ] Element with `addEventListener` or `querySelector` → `html` snippet widget
- [ ] Swiper / GSAP / Chart.js component → `html` snippet widget with full `<script>` preserved
- [ ] CSS custom properties (`--color-primary`) inside a component → `html` snippet widget
- [ ] Simple `style="padding:20px"` on a heading → native `heading` widget (NOT html snippet)
- [ ] HTML snippet widget renders correctly in Elementor preview without JS console errors
- [ ] Multiple `<script>` tags in one component are merged before bundling into html snippet
