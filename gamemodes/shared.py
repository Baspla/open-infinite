import logging
from gamemodes.gamemode import BasicGamemode
from templates import gamemode, item, item_list, pair_result, username, clear, news, pair_empty_result

log = logging.getLogger('SharedGamemode')

class SharedGamemode(BasicGamemode):

    def __init__(self, game_controller):
        super().__init__(game_controller)
        self.shared_item_pool = [item("Water", "💧"), item("Fire", "🔥"), item("Earth", "🌍"), item("Air", "💨")]

    async def start(self):
        log.info('Shared Gamemode started')
        await self.send(clear())
        await self.send(gamemode("Shared"))
        await self.send(news(""))
        for uuid in self.game_controller.players:
            await self.send(username(self.getName(uuid)), uuid)
            await self.send(item_list(self.shared_item_pool), uuid)

    async def end(self):
        log.info('Shared Gamemode ended')

    async def stop(self):
        log.info('Shared Gamemode stopped')

    def get_item_pool(self):
        return self.shared_item_pool

    def add_item_to_pool(self, new_item):
        if new_item not in self.shared_item_pool:
            self.shared_item_pool.append(new_item)

    async def join(self, uuid):
        await self.send(clear())
        await self.send(gamemode("Shared"), uuid)
        await self.send(username(self.getName(uuid)), uuid)
        await self.send(item_list(self.shared_item_pool), uuid)
        await self.send(news(f"{self.getName(uuid)} joined the game!"))

    async def pair(self, uuid, pair_id, item1, item2):
        await self.game_controller.request_combo(uuid, pair_id, item1, item2)

    async def handle_combo(self, uuid, pair_id, item1, item2, result, cached):
        if result is not None:
            new_item = item(result.get("name"), result.get("emoji"))
            await self.send(pair_result(pair_id, new_item, not cached), uuid)
            self.add_item_to_pool(new_item)
            # Update alle Spieler mit dem neuen Item-Pool
            for player_uuid in self.game_controller.players:
                await self.send(item_list(self.shared_item_pool), player_uuid)
        else:
            await self.send(pair_empty_result(pair_id), uuid)