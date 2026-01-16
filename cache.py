import json
import os
from typing import Optional


class Cache:
    def __init__(self, combo_file: str = 'cache/combocache.json', item_file: str = 'cache/itemcache.json'):
        self.combocache = {}
        self.itemcache = {}
        self.combo_file = combo_file
        self.item_file = item_file

    def _normalize_key(self, item1: str, item2: str) -> str:
        a = (item1 or '').strip().lower()
        b = (item2 or '').strip().lower()
        first, second = sorted([a, b])
        return f"{first}|{second}"

    def _is_none_value(self, value: Optional[str]) -> bool:
        return value is None or (isinstance(value, str) and value.strip().lower() == "none")

    def find_existing_name(self, name: Optional[str]) -> Optional[str]:
        if not isinstance(name, str):
            return None
        target = name.strip().lower()
        if not target:
            return None

        for existing in self.itemcache.keys():
            if isinstance(existing, str) and existing.strip().lower() == target:
                return existing

        for existing in self.combocache.values():
            if isinstance(existing, str) and existing.strip().lower() == target:
                return existing

        return None

    def get_item_emoji(self, name: str):
        emoji = self.itemcache.get(name)
        if isinstance(emoji, list):
            return emoji[0] if emoji else None
        if isinstance(emoji, str) and not emoji.strip():
            return None
        return emoji

    def get_combo(self, item1: str, item2: str):
        key = self._normalize_key(item1, item2)
        if key in self.combocache:
            result = self.combocache[key]
            if self._is_none_value(result):
                self.combocache[key] = None
                return {"name": None, "emoji": None}
            emoji = self.get_item_emoji(result)
            return {"name": result, "emoji": emoji}
        return None

    def add_combo(self, item1: str, item2: str, result_name: Optional[str], result_emoji: Optional[str]):
        key = self._normalize_key(item1, item2)
        if self._is_none_value(result_name):
            self.combocache[key] = None
            return

        resolved_name = self.find_existing_name(result_name) or result_name
        result_name = resolved_name
        self.combocache[key] = result_name
        if result_emoji is not None and result_name is not None:
            self.set_item_emoji(result_name, result_emoji)

    def set_item_emoji(self, name: str, emoji: str):
        if self._is_none_value(name) or emoji is None or (isinstance(emoji, str) and not emoji.strip()):
            return
        # Overwrite missing or null emoji entries, preserve existing valid ones
        if self.itemcache.get(name) != emoji:
            self.itemcache[name] = emoji

    def _load_mapping(self, path: Optional[str]):
        if not path:
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                print(f"Unexpected JSON structure in {path}, expected an object")
        except FileNotFoundError:
            print(f"No such file: {path}")
        except json.JSONDecodeError:
            print(f"Error decoding JSON from file: {path}")
        return {}

    def _write_mapping(self, path: Optional[str], mapping: dict):
        if not path:
            return
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=True, indent=2)

    def load(self, combo_file: Optional[str] = None, item_file: Optional[str] = None):
        combo_path = combo_file or self.combo_file
        item_path = item_file or self.item_file
        self.combocache = self._load_mapping(combo_path)
        self.itemcache = self._load_mapping(item_path)
        # Purge legacy invalid entries
        for key, value in list(self.combocache.items()):
            if self._is_none_value(value):
                self.combocache[key] = None
        for key in list(self.itemcache.keys()):
            if self._is_none_value(key):
                del self.itemcache[key]

    def save(self, combo_file: Optional[str] = None, item_file: Optional[str] = None):
        combo_path = combo_file or self.combo_file
        item_path = item_file or self.item_file
        self._write_mapping(combo_path, self.combocache)
        self._write_mapping(item_path, self.itemcache)
