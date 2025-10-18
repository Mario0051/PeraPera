import math
import re
from font_manager import get_text_width

def filter_tags(text: str) -> str:
    return re.sub(r'<[^>]*>', '', text)

def add_rbr_tag(text: str) -> str:
    return f"<rbr>{text}"

def add_nb_tag(text: str) -> str:
    return f"<nb>{text}"

def scale_to_width(text: str, max_width: int, default_size: int = None) -> str:
    if not text:
        return text

    filtered_text = filter_tags(text)
    current_width = get_text_width(filtered_text)

    if current_width <= max_width:
        return text

    scale_factor = (max_width / current_width)

    if default_size:
        scaled_size = math.floor(scale_factor * default_size)
        return f"<size={scaled_size}>{text}</size>"
    else:
        scaled_percent = math.floor(scale_factor * 100)
        return f"<sc={scaled_percent}>{text}"

def wrap_to_box(text: str, max_width: int, max_lines: int) -> str:
    if not text:
        return text

    wrapped_text = wrap_text(filter_tags(text), max_width)
    lines = wrapped_text.split('\n')

    if len(lines) > max_lines:
        wrapped_text = "\n".join(lines[:max_lines])

    return wrapped_text.replace('\n', '\\n')

POSTPROCESS_RULES = {
    ("text_data", "7"): [(scale_to_width, (9200,)), (add_nb_tag,)],
    ("text_data", "6"): [(scale_to_width, (9500,))],
    ("text_data", "170"): [(scale_to_width, (9500,))],
    ("text_data", "76"): [(scale_to_width, (14800,))],
    ("text_data", "47"): [(scale_to_width, (13110,))],
    ("text_data", "48"): [(wrap_to_box, (18630, 4)), (add_rbr_tag,)],
    ("story", "name"): [(scale_to_width, (12420,))],
    ("story", "choice"): [(scale_to_width, (20150, 44))],
    ("story", "text"): [(None, (19500,))],
    ("text_data", "92"): [(scale_to_width, (19120,)), (add_nb_tag,)],
    ("text_data", "94"): [(scale_to_width, (19120,)), (add_nb_tag,)],
}

def apply_postprocess(asset_type: str, category_id: str, text: str) -> str:
    if not text:
        return text

    category_id = str(category_id)

    rules = POSTPROCESS_RULES.get((asset_type, category_id))
    if not rules:
        return text

    processed_text = text
    for func, *args in rules:
        if args:
            processed_text = func(processed_text, *args[0])
        else:
            processed_text = func(processed_text)

    return processed_text