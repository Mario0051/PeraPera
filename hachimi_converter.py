from postprocess import apply_postprocess

def _convert_story_format(data: dict) -> dict:
    hachimi_data = {
        "no_wrap": True,
        "text_block_list": []
    }

    if "title" in data:
        en_title = data.get("enTitle") or data.get("title")
        if en_title:
             hachimi_data["title"] = en_title

    for block in data.get("text_blocks", []):
        hachimi_block = {}

        jp_name = block.get("jpName", "").strip()
        if jp_name and jp_name != "モノローグ":
            en_name = block.get("enName", "").strip()
            final_name = en_name or jp_name
            if final_name:
                processed_name = apply_postprocess("story", "name", final_name)
                hachimi_block["name"] = processed_name

        en_text = block.get("enText", "").strip()
        jp_text = block.get("jpText", "").strip()
        final_text = en_text or jp_text
        if final_text:
            import re
            color_text_list = []
            matches = re.findall(r'\[c=(\d+)\](.*?)\[/c\]', final_text)
            for match in matches:
                color_id, text_content = match
                color_text_list.append(text_content)

            processed_text = re.sub(r'\[c=\d+\](.*?)\[/c\]', r'\1', final_text)
            hachimi_block["text"] = processed_text

            if color_text_list:
                hachimi_block["color_text_info_list"] = color_text_list

        if "choices" in block and block["choices"]:
            choice_list = []
            for choice in block["choices"]:
                en_choice = choice.get("enText", "").strip()
                jp_choice = choice.get("jpText", "").strip()
                final_choice = en_choice or jp_choice

                if final_choice:
                    processed_choice = apply_postprocess("story", "choice", final_choice)
                    choice_list.append(processed_choice)

            if choice_list:
                hachimi_block["choice_data_list"] = choice_list

        if "coloredText" in block and block["coloredText"]:
            color_text_list = []
            for color_info in block["coloredText"]:
                en_color_text = color_info.get("enText", "").strip()
                jp_color_text = color_info.get("jpText", "").strip()
                final_color_text = en_color_text or jp_color_text
                if final_color_text:
                    color_text_list.append(final_color_text)

            if color_text_list:
                hachimi_block["color_text_info_list"] = color_text_list

        if hachimi_block:
            hachimi_data["text_block_list"].append(hachimi_block)

    return hachimi_data

def _convert_lyrics_format(data: dict) -> dict:
    hachimi_data = {}
    for block in data.get("text_blocks", []):
        timestamp = block.get("time")
        en_text = block.get("enText", "").strip()
        jp_text = block.get("jpText", "").strip()

        final_text = en_text or jp_text

        if timestamp and final_text:
            hachimi_data[timestamp] = final_text

    return hachimi_data

def _convert_uianimation_format(data: dict) -> dict:
    hachimi_data = {}
    patch_data = {"motion_parameter_list": {}}

    for block in data.get("text_blocks", []):
        en_text = block.get("enText", "").strip()

        if en_text:
            motion_idx_str = str(block["motion_index"])
            text_idx_str = str(block["text_index"])

            if motion_idx_str not in patch_data["motion_parameter_list"]:
                patch_data["motion_parameter_list"][motion_idx_str] = {"text_param_list": {}}

            patch_data["motion_parameter_list"][motion_idx_str]["text_param_list"][text_idx_str] = {
                "text": en_text.replace('\\n', '\n')
            }

    if patch_data["motion_parameter_list"]:
        if "bundle_hashes" in data:
            for platform, bhash in data["bundle_hashes"].items():
                hachimi_data[platform.lower()] = {"bundle_name": bhash}
        hachimi_data["data"] = patch_data

    return hachimi_data

def convert_to_hachimi_format(data: dict) -> dict:
    asset_type = data.get("type")

    if asset_type == "lyrics":
        return _convert_lyrics_format(data)
    elif asset_type == "uianimation":
        return _convert_uianimation_format(data)
    else:
        return _convert_story_format(data)