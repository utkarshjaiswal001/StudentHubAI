"""Generate dark-auto.css (dark versions of hard-coded light colours) and
light-auto.css (soft surfaces instead of pure white in light mode).

The old stylesheets (style.css, pages.css, login.css, theme.css) use many fixed
colours such as `background: #fff`. This script finds them and writes matching
rules that only apply when <html data-theme="dark">. Hand-tuned dark styles
live in dark.css, which loads after this file.

Run from the project root:  python tools/make_dark_css.py
"""

import colorsys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ["style.css", "pages.css", "login.css", "theme.css"]
OUT = ROOT / "static" / "css" / "dark-auto.css"
PREFIX = 'html[data-theme="dark"]'

NAMED = {"white": "#ffffff", "black": "#000000"}
COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|\bwhite\b|\bblack\b")
LIGHT_BG_VARS = {"var(--white)", "var(--background)", "var(--classic-surface)", "var(--classic-background)"}


def parse_color(token):
    token = NAMED.get(token, token)
    if token.startswith("#"):
        h = token[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return r, g, b, a
    parts = [p.strip() for p in token[token.index("(") + 1:-1].replace("/", ",").split(",")]
    if len(parts) < 3:
        return None
    try:
        r, g, b = (float(p) / 255 for p in parts[:3])
        a = float(parts[3]) if len(parts) > 3 else 1.0
    except ValueError:
        return None
    return r, g, b, a


def fmt(r, g, b, a=1.0):
    r, g, b = (max(0, min(255, round(v * 255))) for v in (r, g, b))
    if a >= 0.999:
        return f"#{r:02x}{g:02x}{b:02x}"
    return f"rgba({r}, {g}, {b}, {a:.2f})"


def band(h, s):
    """Which palette colour a fixed brand colour should follow (None = keep it).

    Violet/blue -> --c1, cyan/teal and pink -> --c2, orange/amber -> --c3.
    Green and red stay as they are: they mean "success" and "error".
    """
    if s < 0.25:
        return None
    hue = h * 360
    if 200 <= hue <= 290:
        return "--c1"
    if 170 <= hue < 200 or 290 < hue <= 345:
        return "--c2"
    if 15 <= hue < 60:
        return "--c3"
    return None


def themed(token, use):
    """Swap a fixed brand colour for the same strength of the palette colour.

    use: "bg" (backgrounds), "text", "line" (borders, outlines, shadows).
    Returns None when the colour should be left to the other rules.
    """
    c = parse_color(token)
    if c is None:
        return None
    r, g, b, a = c
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    var = band(h, s)
    if var is None or l > 0.985:
        return None
    if a < 0.999:
        if l < 0.3:
            return None  # dark shadow or overlay
        return f"rgba(var({var}), {a:.2f})"
    if l > 0.8:  # pastel tint
        if use == "text":
            return f"color-mix(in srgb, rgb(var({var})) 35%, #fff)"
        pct = max(5, min(35, round((1 - l) * 220)))
        return f"color-mix(in srgb, rgb(var({var})) {pct}%, var(--surface))"
    if l < 0.5:  # deep colour (dark banners, deep text)
        pct = max(25, min(90, round(l / 0.6 * 100)))
        return f"color-mix(in srgb, rgb(var({var})) {pct}%, #05060a)"
    return f"rgb(var({var}))"


def dark_background(token):
    """Light surfaces become the palette's dark surfaces; brand colours follow the palette."""
    c = parse_color(token)
    if c is None:
        return token
    r, g, b, a = c
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    var = band(h, s)
    if l < 0.62:
        return themed(token, "bg") or token  # strong colours (banners, buttons, badges)
    if a < 0.999 and s > 0.15 and l < 0.985:
        return themed(token, "bg") or token  # faint colour tints work on dark too
    if a < 0.999:
        # Light glass overlays: dark glass for strong ones, faint light for subtle ones.
        if a >= 0.5:
            return f"color-mix(in srgb, var(--surface) {round(a * 100)}%, transparent)"
        return fmt(1, 1, 1, round(a * 0.18, 2))
    if s < 0.12 or l > 0.985:
        return "var(--surface)" if l > 0.97 else "var(--surface-2)"
    return f"color-mix(in srgb, rgb(var({var or '--c1'})) 10%, var(--surface))"


def light_background(token):
    """Light mode: near-white surfaces use the palette's soft surface; brand tints follow the palette."""
    c = parse_color(token)
    if c is None:
        return token
    r, g, b, a = c
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if l < 0.975:
        return themed(token, "bg") or token
    if a < 0.999:
        return f"color-mix(in srgb, var(--surface) {round(a * 100)}%, transparent)" if a >= 0.5 else token
    return "var(--surface)"


def light_text(token):
    """Light mode: brand-coloured text follows the palette (deep shades for readability)."""
    c = parse_color(token)
    if c is None:
        return token
    r, g, b, a = c
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    var = band(h, s)
    if var == "--c1" and 0.25 <= l <= 0.7 and a >= 0.999:
        return "var(--primary-dark)"
    return themed(token, "text") or token


def light_line(token):
    return themed(token, "line") or token


def dark_text(token):
    """Dark text becomes light; brand-coloured text uses the palette's colours."""
    c = parse_color(token)
    if c is None:
        return token
    r, g, b, a = c
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    var = band(h, s)
    if l > 0.7:
        return themed(token, "text") or token  # already light (e.g. white text on buttons)
    if s > 0.35:
        if var == "--c1":
            return "var(--primary-dark)"
        if var:
            return f"color-mix(in srgb, rgb(var({var})) 70%, #fff)"
        return fmt(*colorsys.hls_to_rgb(h, 0.76, min(s, 0.85)), a)
    if l < 0.35:
        return "var(--dark)"
    return "var(--muted)"


def dark_border(token):
    c = parse_color(token)
    if c is None:
        return token
    r, g, b, a = c
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if l < 0.6:
        return themed(token, "line") or token
    if a < 0.999 and s > 0.25:
        return themed(token, "line") or token
    return fmt(1, 1, 1, 0.09 if a >= 0.5 else 0.06)


BG_PROPS = ("background", "background-color", "background-image")
TEXT_PROPS = ("color", "fill", "caret-color", "accent-color")
SHADOW_PROPS = ("box-shadow", "text-shadow")


def convert(prop, value, mode="dark"):
    prop = prop.lower()
    sub = lambda fn: COLOR_RE.sub(lambda m: fn(m.group(0)), value)
    if mode == "light":
        if prop in BG_PROPS:
            if value.strip() in ("var(--white)", "var(--classic-surface)"):
                return "var(--surface)"
            return sub(light_background)
        if prop in TEXT_PROPS:
            return sub(light_text)
        if prop.startswith("border") or prop.startswith("outline") or prop in SHADOW_PROPS:
            return sub(light_line)
        return value
    if prop in BG_PROPS:
        if value.strip() in LIGHT_BG_VARS:
            return "var(--surface)"
        return sub(dark_background)
    if prop in TEXT_PROPS:
        return sub(dark_text)
    if prop.startswith("border") or prop in ("outline", "outline-color"):
        return sub(dark_border)
    if prop in SHADOW_PROPS:
        return sub(lambda t: themed(t, "line") or t)
    return value


def split_rules(css):
    """Yield (selector, body, media) for simple and one-level @media rules."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    i, n = 0, len(css)
    media_stack = []
    while i < n:
        brace = css.find("{", i)
        close = css.find("}", i)
        if close != -1 and (brace == -1 or close < brace):
            if media_stack:
                media_stack.pop()
            i = close + 1
            continue
        if brace == -1:
            break
        head = css[i:brace].strip()
        if head.startswith("@media") or head.startswith("@supports"):
            media_stack.append(head)
            i = brace + 1
            continue
        end = css.find("}", brace)
        body = css[brace + 1:end]
        if not head.startswith("@") and "keyframes" not in head and not re.fullmatch(r"[\d.%,\s]+|from|to", head):
            yield head, body, media_stack[-1] if media_stack else None
        elif head.startswith("@keyframes") or head.startswith("@font-face"):
            # Skip the whole block.
            depth, j = 1, brace + 1
            while depth and j < n:
                depth += {"{": 1, "}": -1}.get(css[j], 0)
                j += 1
            i = j
            continue
        i = end + 1


def prefix_selector(selector, prefix=PREFIX):
    out = []
    for part in selector.split(","):
        part = " ".join(part.split())
        if not part:
            continue
        if part == ":root":
            continue
        if part.startswith("html"):
            out.append(prefix + part[4:])
        else:
            out.append(f"{prefix} {part}")
    return ",\n".join(out)


def build(mode, out, prefix):
    blocks = []
    for name in SOURCES:
        css = (ROOT / "static" / "css" / name).read_text(encoding="utf-8")
        for selector, body, media in split_rules(css):
            changes = []
            for decl in body.split(";"):
                if ":" not in decl:
                    continue
                prop, value = decl.split(":", 1)
                prop, value = prop.strip(), " ".join(value.split())
                if prop.startswith("--"):
                    continue
                new = convert(prop, value, mode)
                if new != value:
                    changes.append(f"    {prop}: {new};")
            sel = prefix_selector(selector, prefix)
            if changes and sel:
                rule = f"{sel} {{\n" + "\n".join(changes) + "\n}"
                if media:
                    rule = f"{media} {{\n{rule}\n}}"
                blocks.append(f"/* {name} */\n{rule}")
    out.write_text(
        "/* Generated by tools/make_dark_css.py. Do not edit by hand;\n"
        "   put hand-made theme styles in dark.css or theme-ui.css instead. */\n\n" + "\n\n".join(blocks) + "\n",
        encoding="utf-8",
        newline="\n",  # same line endings on Windows and Linux
    )
    print(f"{len(blocks)} rules -> {out.relative_to(ROOT)}")


def main():
    build("dark", OUT, 'html[data-theme="dark"]')
    build("light", ROOT / "static" / "css" / "light-auto.css", 'html[data-theme="light"]')


if __name__ == "__main__":
    main()
