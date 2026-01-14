import logging
from gamemodes.gamemode import AbstractGamemode
from templates import item, item_list, news

log = logging.getLogger('SharedGamemode')


class SharedGamemode(AbstractGamemode):

    def __init__(self, game_controller):
        super().__init__(game_controller, "Shared")
        self.shared_item_pool = [item("Water", "💧"), item("Fire", "🔥"), item("Earth", "🌍"), item("Air", "💨")]

    def get_item_pool(self, uuid):
        return self.shared_item_pool

    def add_item_to_pool(self, uuid, new_item):
        if new_item not in self.shared_item_pool:
            self.shared_item_pool.append(new_item)

    async def join(self, uuid):
        await super().join(uuid)
        await self.send(news(f"{self.get_player_name(uuid)} joined the game!"))

    async def broadcast_item_list(self, uuid):
        for player_uuid in self.game_controller.players:
            await self.send(item_list(self.shared_item_pool), player_uuid)