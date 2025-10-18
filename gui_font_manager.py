from pathlib import Path
from PySide6.QtGui import QFont, QFontDatabase

from config import WORKSPACE_DIR

FONT_PATH = WORKSPACE_DIR / "font" / "dynamic01.otf"
UMA_FONT_FAMILY = None

def get_gui_font(font_size: int = 16, weight: QFont.Weight = QFont.Weight.Normal, italic: bool = False) -> QFont:
    global UMA_FONT_FAMILY

    if UMA_FONT_FAMILY is None:
        if not FONT_PATH.exists():
            print("WARNING: Font file not found at 'translations/font/dynamic01.otf'. GUI will use default system font.")
            print("-> You can export the font by running: perapera.py export font")
            UMA_FONT_FAMILY = "fallback" 
        else:
            font_id = QFontDatabase.addApplicationFont(str(FONT_PATH))
            if font_id == -1:
                print(f"ERROR: Failed to load font: {FONT_PATH}")
                UMA_FONT_FAMILY = "fallback"
            else:
                UMA_FONT_FAMILY = QFontDatabase.applicationFontFamilies(font_id)[0]

    if UMA_FONT_FAMILY != "fallback":
        font = QFont(UMA_FONT_FAMILY, font_size, weight, italic)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        return font
    else:
        return QFont("sans-serif", font_size, weight, italic)