import logging
from gamemodes.bingo import BingoGamemode
from templates import item, item_list

log = logging.getLogger('SharedBingoGamemode')


class SharedBingoGamemode(BingoGamemode):
    def __init__(self, game_controller, config=None):
        config = config or {}
        super().__init__(game_controller, config)
        # Prefix to distinguish from regular bingo in UI and logs
        self.mode_name = f"Shared {self.mode_name}"
        self.shared_item_pool = self._default_pool()

    def get_item_pool(self, uuid):
        return self.shared_item_pool

    def add_item_to_pool(self, uuid, new_item):
        if new_item not in self.shared_item_pool:
            self.shared_item_pool.append(new_item)

    async def broadcast_item_list(self, uuid):
        for player_uuid in self.game_controller.players:
            await self.send(item_list(self.shared_item_pool), player_uuid)
