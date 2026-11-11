"""Generate dark-auto.css (dark versions of hard-coded light colours) and
light-auto.css (soft surfaces instead of pure white in light mode).

The old stylesheets (style.css, pages.css, login.css, theme.css) use many fixed
colours such as `background: #fff`. This script finds them and writes matching
rules that only apply when <html data-theme="dark">. Hand-tuned dark styles
live in dark.css, which loads after this file.

Run from the project root:  python .studenthub-build/make_dark_css.py
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


def dark_background(token):
    """Light surfaces become the palette's dark surfaces; pastel tints get a hint of the palette colour."""
    c = parse_color(token)
    if c is None:
        return token
    r, g, b, a = c
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if l < 0.62:
        return token  # already dark or a strong colour (buttons, badges): keep
    if a < 0.999 and s > 0.15 and l < 0.985:
        return token  # faint colour tints work on dark too
    if a < 0.999:
        # Light glass overlays: dark glass for strong ones, faint light for subtle ones.
        if a >= 0.5:
            return f"color-mix(in srgb, var(--surface) {round(a * 100)}%, transparent)"
        return fmt(1, 1, 1, round(a * 0.18, 2))
    if s < 0.12 or l > 0.985:
        return "var(--surface)" if l > 0.97 else "var(--surface-2)"
    return "color-mix(in srgb, rgb(var(--c1)) 10%, var(--surface))"


def light_background(token):
    """Light mode: pure/near-white surfaces use the palette's soft surface instead of #fff."""
    c = parse_color(token)
    if c is None:
        return token
    r, g, b, a = c
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if l < 0.975:
        return token  # tinted pastels, strong colours and dark colours stay as they are
    if a < 0.999:
        return f"color-mix(in srgb, var(--surface) {round(a * 100)}%, transparent)" if a >= 0.5 else token
    return "var(--surface)"


def dark_text(token):
    """Dark text becomes light; brand-coloured text uses the palette's link colour."""
    c = parse_color(token)
    if c is None:
        return token
    r, g, b, a = c
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if l > 0.7:
        return token  # already light (e.g. white text on buttons)
    if s > 0.35:
        if 200 <= h * 360 <= 290:
            return "var(--primary-dark)"
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
        return token
    return fmt(1, 1, 1, 0.09 if a >= 0.5 else 0.06)


def convert(prop, value, mode="dark"):
    prop = prop.lower()
    if mode == "light":
        if prop not in ("background", "background-color", "background-image"):
            return value
        if value.strip() in ("var(--white)", "var(--classic-surface)"):
            return "var(--surface)"
        return COLOR_RE.sub(lambda m: light_background(m.group(0)), value)
    if prop in ("background", "background-color", "background-image"):
        if value.strip() in LIGHT_BG_VARS:
            return "var(--surface)"
        return COLOR_RE.sub(lambda m: dark_background(m.group(0)), value)
    if prop in ("color", "fill", "caret-color"):
        return COLOR_RE.sub(lambda m: dark_text(m.group(0)), value)
    if prop.startswith("border") or prop in ("outline", "outline-color"):
        return COLOR_RE.sub(lambda m: dark_border(m.group(0)), value)
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
        "/* Generated by .studenthub-build/make_dark_css.py. Do not edit by hand;\n"
        "   put hand-made theme styles in dark.css or theme-ui.css instead. */\n\n" + "\n\n".join(blocks) + "\n",
        encoding="utf-8",
    )
    print(f"{len(blocks)} rules -> {out.relative_to(ROOT)}")


def main():
    build("dark", OUT, 'html[data-theme="dark"]')
    build("light", ROOT / "static" / "css" / "light-auto.css", 'html[data-theme="light"]')


if __name__ == "__main__":
    main()
