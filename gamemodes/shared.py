import json
import logging
import os
from gamemodes.gamemode import AbstractGamemode
from templates import item, item_list, news

log = logging.getLogger('SharedGamemode')


class SharedGamemode(AbstractGamemode):

    def __init__(self, game_controller):
        super().__init__(game_controller, "Shared")
        self.pool_file = os.getenv('SHARED_POOL_FILE', 'cache/shared_item_pool.json')
        self.shared_item_pool = self._load_pool()
        self._save_pool()

    def _default_pool(self):
        return [item("Water", "💧"), item("Fire", "🔥"), item("Earth", "🌍"), item("Air", "💨")]

    def _load_pool(self):
        if not self.pool_file:
            return self._default_pool()
        try:
            with open(self.pool_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                cleaned = []
                for entry in data:
                    if isinstance(entry, dict) and entry.get('name'):
                        cleaned.append(item(entry.get('name'), entry.get('emoji')))
                if cleaned:
                    return cleaned
            log.warning('Invalid or empty shared pool file %s', self.pool_file)
        except FileNotFoundError:
            log.info('No existing shared pool file at %s', self.pool_file)
        except Exception as exc:
            log.error('Failed to load shared item pool from %s: %s', self.pool_file, exc)
        return self._default_pool()

    def _save_pool(self):
        if not self.pool_file:
            return
        try:
            os.makedirs(os.path.dirname(self.pool_file) or '.', exist_ok=True)
            with open(self.pool_file, 'w', encoding='utf-8') as f:
                json.dump(self.shared_item_pool, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            log.error('Failed to save shared item pool to %s: %s', self.pool_file, exc)

    def get_item_pool(self, uuid):
        return self.shared_item_pool

    def add_item_to_pool(self, uuid, new_item):
        if new_item not in self.shared_item_pool:
            self.shared_item_pool.append(new_item)
            self._save_pool()

    async def join(self, uuid):
        await super().join(uuid)
        await self.send(news(f"{self.get_player_name(uuid)} joined the game!"))

    async def broadcast_item_list(self, uuid):
        for player_uuid in self.game_controller.players:
            await self.send(item_list(self.shared_item_pool), player_uuid)