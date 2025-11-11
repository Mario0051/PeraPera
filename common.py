from dataclasses import dataclass, field
from pathlib import Path

MDB_TABLE_SCHEMAS = {
    "text_data": ["category", "index", "text"],
    "character_system_text": ["character_id", "voice_id", "text"],
    "race_jikkyo_comment": ["id", "message"],
    "race_jikkyo_message": ["id", "message"]
}

def sanitize_filename(name):
    if not name: return ""
    name = name.replace('\\', '_').replace('/', '_')
    invalid_chars = '<>:"|?*\n\r\t'
    for char in invalid_chars:
        name = name.replace(char, '')
    return name.strip()

@dataclass
class StoryId:
    type: str
    set: str = "00"
    group: str = "0000"
    id: str = "000000000"
    idx: str = "00"
    group_name: str | None = field(default=None, compare=False)

    @staticmethod
    def parse_from_path(asset_type, path_str, group_name=None):
        parts = path_str.split('/')
        filename = parts[-1]

        story_id = StoryId(type=asset_type)
        story_id.group_name = group_name

        if asset_type == "story":
            story_id.group = parts[2]
            story_id.id = parts[3]
            story_id.idx = filename.split('_')[-1]
        elif asset_type == "home":
             story_id.set = parts[2]
             story_id.group = parts[3]
             story_id.id = filename.split('_')[-1]
        elif asset_type == "race":
            story_id.id = filename.split('_')[1]
            story_id.group = story_id.id[:4]
        elif asset_type == "lyrics":
            story_id.id = parts[-1].replace("m", "").replace("_lyrics", "")
            story_id.group = story_id.id
        elif asset_type == "preview":
            story_id.id = filename.split('_')[-1]
            story_id.group = story_id.id
        elif asset_type == "uianimation":
            story_id.id = path_str
            story_id.group = parts[1] if len(parts) > 1 else "" # e.g. "flash"
        else:
            story_id.id = Path(path_str).name

        return story_id

    @staticmethod
    def parse_from_filename(asset_type, filename, group_name=None):
        story_id = StoryId(type=asset_type, group_name=group_name)
        parts = Path(filename).stem.split('_')

        if asset_type in ["story", "home"]:
            story_id.group = parts[0]
            if asset_type == "home":
                story_id.set = parts[0][:5]
                story_id.id = "_".join(parts[-3:])
            else:
                story_id.idx = parts[-1]
        elif asset_type in ["lyrics", "race"]:
            story_id.id = parts[0]
            story_id.group = story_id.id[:4] if asset_type == "race" else story_id.id
        else:
            story_id.id = Path(filename).stem

        return story_id

    def get_output_path(self):
        if self.type == "story":
            return Path(self.type) / self.group / self.id
        elif self.type == "home":
             return Path(self.type) / self.set / self.group
        elif self.type == "generic" or self.type == "uianimation":
             return Path(Path(self.id).parent)
        else:
            return Path(self.type)

    def get_filename_prefix(self):
         sanitized_group_name = sanitize_filename(self.group_name) if self.group_name else None

         if self.type == "story" or self.type == "home":
             prefix_parts = [self.group]
             if sanitized_group_name: prefix_parts.append(sanitized_group_name)
             prefix_parts.append(self.id if self.type == "home" else self.idx)
             return "_".join(prefix_parts)
         elif self.type == "generic" or self.type == "uianimation":
             return Path(self.id).stem
         elif self.type == "lyrics" or self.type == "race":
             prefix_parts = [self.id]
             return "_".join(prefix_parts)
         else:
             return self.id

    def matches_filter(self, filter_group, filter_id):
        if filter_group and self.group != filter_group:
            return False
        if filter_id and self.id != filter_id:
            if self.type == "story" and self.idx != filter_id:
                return False
            elif self.type == "home" and not self.id.endswith(filter_id):
                 return False
            elif self.type not in ["story", "home"] and self.id != filter_id:
                 return False
        return True

    def __str__(self):
        name_part = f", Name: {self.group_name}" if self.group_name else ""
        return f"(Type: {self.type}, Group: {self.group}, ID: {self.id}, Index/Part: {self.idx}{name_part})"