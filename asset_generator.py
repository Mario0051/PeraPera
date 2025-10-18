import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from fontTools.ttLib import TTFont

from api import PeraPeraAPI
from config import WORKSPACE_DIR

GACHA_NAME_FONT_SIZE = 180
GACHA_NAME_MAX_WIDTH = 1450
GACHA_NAME_IMG_SIZE = (2048, 512)
GACHA_NAME_SHEER_FACTOR = 0.2
GACHA_NAME_COLORS = (
    (
        ((148,166,189),),
        ((170,199,218),)
    ),
    (
        ((189,138,8),),
        ((236,178,8),)
    ),
    (
        ((198,77,214),(181,89,214),(107,109,222),(33,142,222),(33,186,148),(57,207,82),(181,215,90)),
        ((227,75,238), (208,97,248),(126,129,255),(33,162,254),(31,220,169),(57,247,90),(202,247,41))
    ),
)

GACHA_COMMENT_MAX_WIDTH = 1760
GACHA_COMMENT_IMG_SIZE = (2048, 512)
GACHA_COMMENT_FONT_SIZE = 120
GACHA_COMMENT_COLORS = (
    ((206,109,183),(206,109,183),(214,109,214),(198,121,214),(115,142,206),(74,182,206),(82,195,165),(99,199,74),(180,198,15),(180,198,15)),
    ((247,141,220),(247,141,220),(252,129,247),(239,140,255),(137,181,255),(84,219,249),(83,247,199),(115,253,90),(228,251,16),(228,251,16)),
)

class Point:
    def __init__(self, x, y): self.x, self.y = x, y

class Rect:
    def __init__(self, x1, y1, x2, y2):
        self.min = Point(min(x1, x2), min(y1, y2))
        self.max = Point(max(x1, x2), max(y1, y2))
    @property
    def width(self): return self.max.x - self.min.x
    @property
    def height(self): return self.max.y - self.min.y

def gradient_color(minval, maxval, val, color_palette):
    max_index = len(color_palette) - 1
    delta = maxval - minval if maxval - minval != 0 else 1
    v = float(val - minval) / delta * max_index
    i1, i2 = int(v), min(int(v) + 1, max_index)
    (r1, g1, b1), (r2, g2, b2) = color_palette[i1], color_palette[i2]
    f = v - i1
    return int(r1 + f * (r2 - r1)), int(g1 + f * (g2 - g1)), int(b1 + f * (b2 - b1))

def horz_gradient(draw, rect, color_func, color_palette):
    minval, maxval = 1, len(color_palette)
    delta = maxval - minval
    for x in range(rect.min.x, rect.max.x + 1):
        f = (x - rect.min.x) / rect.width
        val = minval + f * delta
        color = color_func(minval, maxval, val, color_palette)
        draw.line([(x, rect.min.y), (x, rect.max.y)], fill=color)

def generate_gacha_name_img(text: str, rarity: int, font_path: Path) -> Image.Image:
    rarity = max(1, min(3, rarity))
    palette1 = GACHA_NAME_COLORS[rarity - 1][0]
    palette2 = GACHA_NAME_COLORS[rarity - 1][1]

    font = ImageFont.truetype(str(font_path), GACHA_NAME_FONT_SIZE)
    text_width = font.getbbox(text)[2]

    if text_width > GACHA_NAME_MAX_WIDTH:
        new_size = math.floor(GACHA_NAME_FONT_SIZE * GACHA_NAME_MAX_WIDTH / text_width)
        font = ImageFont.truetype(str(font_path), new_size)
        text_width = font.getbbox(text)[2]

    text_layer = Image.new("RGBA", GACHA_NAME_IMG_SIZE)
    draw = ImageDraw.Draw(text_layer)
    draw.text((GACHA_NAME_IMG_SIZE[0]/2, GACHA_NAME_IMG_SIZE[1]/2), text, font=font, anchor="mm", fill=(255,255,255,255))

    text_layer = text_layer.resize((GACHA_NAME_IMG_SIZE[0], int(GACHA_NAME_IMG_SIZE[1] * 0.9)), Image.Resampling.BICUBIC)
    squeezed_layer = Image.new("RGBA", GACHA_NAME_IMG_SIZE)
    squeezed_layer.paste(text_layer, (0, int(GACHA_NAME_IMG_SIZE[1] * 0.05)))
    sheared_layer = squeezed_layer.transform(GACHA_NAME_IMG_SIZE, Image.Transform.AFFINE, (1, GACHA_NAME_SHEER_FACTOR, -50, 0, 1, 0))
    final_text_layer = sheared_layer.filter(ImageFilter.GaussianBlur(1))

    alpha_mask = final_text_layer.split()[3]
    shadow1_mask = alpha_mask.filter(ImageFilter.GaussianBlur(4)).point(lambda p: 255 if p > 0 else 0)
    shadow2_mask = alpha_mask.filter(ImageFilter.GaussianBlur(15)).point(lambda p: 200 if p > 0 else 0)

    bg_bbox = Rect(int(GACHA_NAME_IMG_SIZE[0]/2 - text_width/2 - 70), 0, int(GACHA_NAME_IMG_SIZE[0]/2 + text_width/2 + 70), GACHA_NAME_IMG_SIZE[1])

    shadow1_bg = Image.new("RGB", GACHA_NAME_IMG_SIZE)
    horz_gradient(ImageDraw.Draw(shadow1_bg), bg_bbox, gradient_color, palette1)
    shadow1_bg.putalpha(shadow1_mask)

    shadow2_bg = Image.new("RGB", GACHA_NAME_IMG_SIZE)
    horz_gradient(ImageDraw.Draw(shadow2_bg), bg_bbox, gradient_color, palette2)
    shadow2_bg.putalpha(shadow2_mask)

    final_image = Image.alpha_composite(Image.new("RGBA", GACHA_NAME_IMG_SIZE), shadow2_bg)
    final_image = Image.alpha_composite(final_image, shadow1_bg)
    final_image = Image.alpha_composite(final_image, final_text_layer)

    return final_image

def _generate_gacha_names(pp_api: PeraPeraAPI):
    pp_api.log.info("Generating Gacha Name images...")

    font_path = WORKSPACE_DIR / "font" / "dynamic01.otf"
    if not font_path.exists():
        pp_api.log.error("Font file not found at 'translations/font/dynamic01.otf'.")
        pp_api.log.error("Please run 'perapera.py export font' first.")
        return

    output_dir = WORKSPACE_DIR / "generated_assets" / "gacha_names"
    output_dir.mkdir(parents=True, exist_ok=True)
    pp_api.log.info(f"Output will be saved to: {output_dir}")

    try:
        text_data = pp_api.load_dict("text_data_dict.json")
    except FileNotFoundError:
        pp_api.log.error("'text_data_dict.json' not found. Please dump tables first.")
        return

    translated_names = {**text_data.get("170", {}), **text_data.get("76", {})}

    asset_list = pp_api.manager.query_asset_names("gacha-charaname")
    asset_list.extend(pp_api.manager.query_asset_names("gacha-supportname"))

    generated_count = 0
    for asset_name in asset_list:
        try:
            parts = asset_name.split('_')
            asset_id = parts[-2]
            rarity = int(parts[-1])

            if asset_id in translated_names and translated_names[asset_id]:
                en_name = translated_names[asset_id]
                pp_api.log.info(f"Generating image for '{en_name}' (ID: {asset_id}, Rarity: {rarity})...")

                img = generate_gacha_name_img(en_name, rarity, font_path)

                output_filename = f"{Path(asset_name).parent.name}_{asset_id}_{rarity}_{en_name.replace(' ', '_')}.png"
                img.save(output_dir / output_filename)
                generated_count += 1
        except (IndexError, ValueError) as e:
            pp_api.log.warn(f"Could not parse asset name '{asset_name}': {e}")
            continue

    if generated_count > 0:
        pp_api.log.info(f"Successfully generated {generated_count} images.")
    else:
        pp_api.log.info("No new images to generate. (Did you translate names in categories 76 and 170?)")

def generate_gacha_comment_img(text: str, font_path: Path) -> Image.Image:
    palette1 = GACHA_COMMENT_COLORS[0]
    palette2 = GACHA_COMMENT_COLORS[1]

    text_layer = Image.new("RGBA", GACHA_COMMENT_IMG_SIZE)
    draw = ImageDraw.Draw(text_layer)

    font = ImageFont.truetype(str(font_path), GACHA_COMMENT_FONT_SIZE)
    text_bbox = draw.multiline_textbbox((0, 0), text, font=font, align='center', spacing=40)
    text_width = text_bbox[2] - text_bbox[0]

    if text_width > GACHA_COMMENT_MAX_WIDTH:
        new_size = math.floor(GACHA_COMMENT_FONT_SIZE * GACHA_COMMENT_MAX_WIDTH / text_width)
        font = ImageFont.truetype(str(font_path), new_size)

    draw.multiline_text((GACHA_COMMENT_IMG_SIZE[0]/2, GACHA_COMMENT_IMG_SIZE[1]/2), text, font=font, anchor="mm", align='center', spacing=40, fill=(255,255,255,255))

    final_text_layer = text_layer.filter(ImageFilter.GaussianBlur(1))

    alpha_mask = final_text_layer.split()[3]
    shadow1_mask = alpha_mask.filter(ImageFilter.GaussianBlur(4)).point(lambda p: 255 if p > 0 else 0)
    shadow2_mask = alpha_mask.filter(ImageFilter.GaussianBlur(15)).point(lambda p: 180 if p > 0 else 0)

    bg_bbox = Rect(int(GACHA_COMMENT_IMG_SIZE[0]/2 - text_width/2 - 70), 0, int(GACHA_COMMENT_IMG_SIZE[0]/2 + text_width/2 + 70), GACHA_COMMENT_IMG_SIZE[1])

    shadow1_bg = Image.new("RGB", GACHA_COMMENT_IMG_SIZE)
    horz_gradient(ImageDraw.Draw(shadow1_bg), bg_bbox, gradient_color, palette1)
    shadow1_bg.putalpha(shadow1_mask)

    shadow2_bg = Image.new("RGB", GACHA_COMMENT_IMG_SIZE)
    horz_gradient(ImageDraw.Draw(shadow2_bg), bg_bbox, gradient_color, palette2)
    shadow2_bg.putalpha(shadow2_mask)

    final_image = Image.alpha_composite(Image.new("RGBA", GACHA_COMMENT_IMG_SIZE), shadow2_bg)
    final_image = Image.alpha_composite(final_image, shadow1_bg)
    final_image = Image.alpha_composite(final_image, final_text_layer)

    return final_image

def _generate_gacha_comments(pp_api: PeraPeraAPI):
    pp_api.log.info("Generating Gacha Comment images...")

    font_path = WORKSPACE_DIR / "font" / "dynamic01.otf"
    if not font_path.exists():
        pp_api.log.error("Font file not found at 'translations/font/dynamic01.otf'. Cannot generate images.")
        return

    output_dir = WORKSPACE_DIR / "generated_assets" / "gacha_comments"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        comment_data = pp_api.load_dict("gacha_comments.json")
    except FileNotFoundError:
        pp_api.log.info("No 'gacha_comments.json' found. Skipping.")
        return

    generated_count = 0
    for asset_id, en_text in comment_data.items():
        if not en_text: continue

        pp_api.log.info(f"Generating image for comment ID {asset_id}...")
        try:
            img = generate_gacha_comment_img(en_text, font_path)
            output_filename = f"gacha_comment_{asset_id}.png"
            img.save(output_dir / output_filename)
            generated_count += 1
        except Exception as e:
            pp_api.log.warn(f"Could not generate image for comment ID {asset_id}: {e}")

    if generated_count > 0:
        pp_api.log.info(f"Successfully generated {generated_count} gacha comment images.")
    else:
        pp_api.log.info("No new gacha comment images to generate.")

def run(args):
    with PeraPeraAPI() as pp_api:
        if args.gacha_names:
            _generate_gacha_names(pp_api)
        elif args.gacha_comments:
            _generate_gacha_comments(pp_api)
        else:
            pp_api.log.warn("No asset generation target specified.")

def add_parser(subparsers):
    parser = subparsers.add_parser(
        "generate-assets",
        help="Generates translated image assets using Pillow.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.set_defaults(func=run)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--gacha-names",
        action="store_true",
        help="Generate translated title images for gacha banners."
    )
    group.add_argument(
        "--gacha-comments",
        action="store_true",
        help="Generate translated comment images for gacha banners."
    )
    return parser