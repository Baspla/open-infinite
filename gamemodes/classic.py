import logging
from statistics import mode
from gamemodes.gamemode import BasicGamemode
from templates import gamemode, item, item_list, pair_result, username, clear, news, pair_empty_result

log = logging.getLogger('ClassicGamemode')


class ClassicGamemode(BasicGamemode):
    
    def __init__(self, game_controller):
        super().__init__(game_controller)
        self.item_pools = {}
    
    async def start(self):
        log.info('Classic Gamemode started')
        await self.send(clear())
        await self.send(gamemode("Classic"))
        await self.send(news(""))
        for uuid in self.game_controller.players:
            await self.send(username(self.getName(uuid)), uuid)
            await self.send(item_list(self.get_item_pool(uuid)), uuid)
        pass
    
    async def end(self):
        log.info('Classic Gamemode ended')
        pass
    
    async def stop(self):
        log.info('Classic Gamemode stopped')
        pass
    
    def get_item_pool(self, uuid):
        if uuid not in self.item_pools:
            self.item_pools[uuid] = [item("Water", "💧"), item("Fire", "🔥"), item("Earth", "🌍"), item("Air", "💨")]
        return self.item_pools[uuid]
    
    def add_item_to_pool(self, uuid, item):
        if item not in self.item_pools[uuid]:
            self.item_pools[uuid].append(item)
    
    async def join(self, uuid):
        await self.send(clear())
        await self.send(gamemode("Classic"), uuid)
        await self.send(username(self.getName(uuid)), uuid)
        await self.send(item_list(self.get_item_pool(uuid)), uuid)
        pass
    
    async def pair(self, uuid, pair_id, item1, item2):
        await self.game_controller.request_combo(uuid, pair_id, item1, item2)
    
    async def handle_combo(self, uuid, pair_id, item1, item2, result, cached):
        if result is not None:
            await self.send(pair_result(pair_id, item(result.get("name"), result.get("emoji")), not cached), uuid)
            self.add_item_to_pool(uuid, item(result.get("name"), result.get("emoji")))
            await self.send(item_list(self.get_item_pool(uuid)), uuid)
        else:
            await self.send(pair_empty_result(pair_id), uuid)
        pass
