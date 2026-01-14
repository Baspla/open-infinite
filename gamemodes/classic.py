import logging
from gamemodes.gamemode import AbstractGamemode
from templates import item

log = logging.getLogger('ClassicGamemode')


class ClassicGamemode(AbstractGamemode):
    def __init__(self, game_controller):
        super().__init__(game_controller, "Classic")
        self.item_pools = {}

    def get_item_pool(self, uuid):
        if uuid not in self.item_pools:
            self.item_pools[uuid] = [item("Water", "💧"), item("Fire", "🔥"), item("Earth", "🌍"), item("Air", "💨")]
        return self.item_pools[uuid]

    def add_item_to_pool(self, uuid, new_item):
        pool = self.get_item_pool(uuid)
        if new_item not in pool:
            pool.append(new_item)
