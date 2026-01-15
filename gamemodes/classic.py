import json
import logging
import os

from gamemodes.gamemode import AbstractGamemode
from templates import item

log = logging.getLogger('ClassicGamemode')


class ClassicGamemode(AbstractGamemode):
    def __init__(self, game_controller):
        super().__init__(game_controller, "Classic")
        self.item_pools = {}
        self.pool_file = os.getenv('CLASSIC_POOL_FILE', 'cache/classic_item_pools.json')
        self._load_pools()

    def _default_pool(self):
        return [item("Water", "💧"), item("Fire", "🔥"), item("Earth", "🌍"), item("Air", "💨")]

    def _load_pools(self):
        if not self.pool_file:
            return
        try:
            with open(self.pool_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                for uuid, entries in data.items():
                    if not isinstance(entries, list):
                        continue
                    cleaned = []
                    for entry in entries:
                        if isinstance(entry, dict) and entry.get('name'):
                            cleaned.append(item(entry.get('name'), entry.get('emoji')))
                    if cleaned:
                        self.item_pools[uuid] = cleaned
            else:
                log.warning('Invalid structure in classic pool file %s', self.pool_file)
        except FileNotFoundError:
            log.info('No existing classic pool file at %s', self.pool_file)
        except Exception as exc:  # pragma: no cover - defensive logging
            log.error('Failed to load classic item pools from %s: %s', self.pool_file, exc)

    def _save_pools(self):
        if not self.pool_file:
            return
        try:
            os.makedirs(os.path.dirname(self.pool_file) or '.', exist_ok=True)
            with open(self.pool_file, 'w', encoding='utf-8') as f:
                json.dump(self.item_pools, f, ensure_ascii=False, indent=2)
        except Exception as exc:  # pragma: no cover - defensive logging
            log.error('Failed to save classic item pools to %s: %s', self.pool_file, exc)

    def get_item_pool(self, uuid):
        if uuid not in self.item_pools:
            self.item_pools[uuid] = self._default_pool()
            self._save_pools()
        return self.item_pools[uuid]

    def add_item_to_pool(self, uuid, new_item):
        pool = self.get_item_pool(uuid)
        if new_item not in pool:
            pool.append(new_item)
            self._save_pools()
