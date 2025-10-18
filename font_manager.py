from pathlib import Path
from fontTools.ttLib import TTFont
from functools import lru_cache
from config import WORKSPACE_DIR
import pyphen

FONT_PATH = WORKSPACE_DIR / "font" / "dynamic01.otf"
HYPHEN_DICT = pyphen.Pyphen(lang='en_US')

@lru_cache(maxsize=None)
def get_font():
    if not FONT_PATH.exists():
        print("WARNING: Font file not found at 'translations/font/dynamic01.otf'. Text scaling will be disabled.")
        return None
    try:
        return TTFont(FONT_PATH)
    except Exception as e:
        print(f"ERROR: Could not load font file: {e}")
        return None

@lru_cache(maxsize=None)
def get_font_glyphset_and_cmap():
    font = get_font()
    if not font:
        return None, None
    return font.getGlyphSet(), font.getBestCmap()

@lru_cache(maxsize=8192)
def get_char_width(char: str) -> float:
    glyphset, cmap = get_font_glyphset_and_cmap()
    if not glyphset or not cmap:
        return 20.0

    if ord(char) in cmap:
        return glyphset[cmap[ord(char)]].width
    return 0.0

def get_text_width(text: str, scale: float = 1.0) -> float:
    if not get_font():
        return len(text) * 20.0

    return sum(get_char_width(char) for char in text) * scale

def wrap_text(text: str, max_width: int, hyphenate: bool = True) -> str:
    words = text.split(" ")
    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}" if current_line else word
        if get_text_width(test_line) <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)

            if get_text_width(word) <= max_width:
                current_line = word
            elif hyphenate:
                hyphenated = False
                for i in range(len(HYPHEN_DICT.inserted(word).split('-')) - 1, 0, -1):
                    syllables = HYPHEN_DICT.inserted(word).split('-')
                    part1 = "".join(syllables[:i]) + "-"
                    part2 = "".join(syllables[i:])
                    if get_text_width(part1) <= max_width:
                        lines.append(part1)
                        current_line = part2
                        hyphenated = True
                        break
                if not hyphenated:
                    lines.append(word)
                    current_line = ""
            else:
                lines.append(word)
                current_line = ""

    if current_line:
        lines.append(current_line)

    return "\n".join(lines)