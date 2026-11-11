"""Every colour set must reach every part of the site.

The original stylesheets use fixed brand colours (violet, cyan, pink, amber).
make_dark_css.py writes theme rules that swap each of them for the palette's own
colours. These tests fail if a fixed brand colour would still show through in
dark or light mode, which is how "the AI Mentor section stays purple in the
green theme" bugs happen.
"""

import colorsys
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("make_dark_css", ROOT / "tools" / "make_dark_css.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

COLOUR_PROPS = gen.BG_PROPS + gen.TEXT_PROPS + gen.SHADOW_PROPS


def fixed_brand_colours(css_text):
    """Yield (selector, property, colour) for brand colours that do not follow the palette."""
    for selector, body, _media in gen.split_rules(css_text):
        for decl in body.split(";"):
            if ":" not in decl:
                continue
            prop, value = (part.strip() for part in decl.split(":", 1))
            prop = prop.lower()
            if prop.startswith("--"):
                continue
            if not (prop in COLOUR_PROPS or prop.startswith("border") or prop.startswith("outline")):
                continue
            for match in gen.COLOR_RE.finditer(value):
                colour = gen.parse_color(match.group(0))
                if colour is None:
                    continue
                r, g, b, a = colour
                h, l, s = colorsys.rgb_to_hls(r, g, b)
                if gen.band(h, s) is None or l > 0.985 or l < 0.08:
                    continue
                if a < 0.999 and l < 0.3:
                    continue  # dark shadow
                yield selector, prop, match.group(0)


class ThemeColourCoverageTests(unittest.TestCase):
    def test_generated_theme_files_are_up_to_date(self):
        css_dir = ROOT / "static" / "css"
        for mode, name in (("dark", "dark-auto.css"), ("light", "light-auto.css")):
            with self.subTest(file=name):
                text = (css_dir / name).read_text(encoding="utf-8")
                for source in gen.SOURCES:
                    for selector, body, _media in gen.split_rules((css_dir / source).read_text(encoding="utf-8")):
                        for decl in body.split(";"):
                            if ":" not in decl:
                                continue
                            prop, value = decl.split(":", 1)
                            prop, value = prop.strip(), " ".join(value.split())
                            if prop.startswith("--"):
                                continue
                            new = gen.convert(prop, value, mode)
                            if new != value:
                                self.assertIn(new, text, f"{name} is out of date for {source} {selector} {prop}. "
                                                         "Run: python tools/make_dark_css.py")

    def test_no_fixed_brand_colour_survives_in_either_mode(self):
        css_dir = ROOT / "static" / "css"
        for mode in ("dark", "light"):
            for source in gen.SOURCES:
                for selector, body, _media in gen.split_rules((css_dir / source).read_text(encoding="utf-8")):
                    for decl in body.split(";"):
                        if ":" not in decl:
                            continue
                        prop, value = decl.split(":", 1)
                        prop, value = prop.strip(), " ".join(value.split())
                        if prop.startswith("--"):
                            continue
                        result = gen.convert(prop, value, mode)
                        leftovers = list(fixed_brand_colours(f"x {{ {prop}: {result}; }}"))
                        with self.subTest(mode=mode, rule=f"{source} {selector[:50]} {prop}"):
                            self.assertEqual(leftovers, [], f"fixed colour {[c for *_, c in leftovers]} ignores the palette")

    def test_hand_written_theme_files_use_palette_colours(self):
        # Theme files written by hand must not hard-code brand colours either.
        css_dir = ROOT / "static" / "css"
        for name in ("dark.css", "theme-ui.css", "layout-glass.css", "fx-shine.css"):
            with self.subTest(file=name):
                leftovers = list(fixed_brand_colours((css_dir / name).read_text(encoding="utf-8")))
                self.assertEqual(leftovers, [], f"{name} has fixed colours: {leftovers[:5]}")


if __name__ == "__main__":
    unittest.main()
