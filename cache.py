import json


class Cache:
    def __init__(self):
        self.combocache = {}
        self.itemcache = {}

    def _normalize_key(self, item1: str, item2: str) -> str:
        a = (item1 or '').strip().lower()
        b = (item2 or '').strip().lower()
        first, second = sorted([a, b])
        return f"{first}|{second}"

    def get_combo(self, item1: str, item2: str):
        key = self._normalize_key(item1, item2)
        result = self.combocache.get(key)
        if not result:
            return None
        emoji = self.itemcache.get(result)
        if isinstance(emoji, list):
            emoji = emoji[0] if emoji else None
        return {"name": result, "emoji": emoji}

    def add_combo(self, item1: str, item2: str, result_name: str, result_emoji: str):
        key = self._normalize_key(item1, item2)
        self.combocache[key] = result_name
        self.itemcache[result_name] = result_emoji

    def load(self, filename):
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                self.combocache = data.get('combocache', {})
                self.itemcache = data.get('itemcache', {})
        except FileNotFoundError:
            print(f"No such file: {filename}")
        except json.JSONDecodeError:
            print(f"Error decoding JSON from file: {filename}")

    def save(self, filename):
        data = {
            'combocache': self.combocache,
            'itemcache': self.itemcache
        }
        with open(filename, 'w') as f:
            json.dump(data, f)
