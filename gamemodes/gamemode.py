import logging
from templates import bingo, clear, gamemode, item, item_list, news, pair_empty_result, pair_result, username

log = logging.getLogger('AbstractGamemode')


class AbstractGamemode:
    """Shared gamemode logic; subclasses only define item-pool strategy."""

    def __init__(self, game_controller, mode_name: str):
        self.game_controller = game_controller
        self.mode_name = mode_name

    async def start(self):
        log.info('%s started', self.mode_name)
        await self._send_state_to_all()

    async def stop(self):
        log.info('%s stopped', self.mode_name)

    async def finish(self):
        log.info('%s finished (admin)', self.mode_name)
        await self.stop()

    async def rejoin(self, uuid):
        log.info('%s rejoined', self.get_player_name(uuid))
        await self.join(uuid)

    async def join(self, uuid):
        log.info('%s joined', self.get_player_name(uuid))
        await self._send_state(uuid)

    async def pair(self, uuid, pair_id, item1, item2):
        log.info('%s paired %s with %s', self.get_player_name(uuid), item1, item2)
        await self.game_controller.request_combo(uuid, pair_id, item1, item2)

    async def handle_combo(self, uuid, pair_id, item1, item2, result, cached):
        if result is None:
            await self.send(pair_empty_result(pair_id), uuid)
            return

        new_item = item(result.get('name'), result.get('emoji'))
        await self._add_item_and_notify(uuid, pair_id, new_item, cached)

    # --- Bingo hooks ---
    async def handle_bingo_click(self, uuid, click_data):
        log.debug('Bingo click ignored in %s mode', self.mode_name)

    def get_bingo_field(self, uuid):
        raise NotImplementedError

    async def send_bingo_field(self, uuid=None, field=None):
        try:
            target_field = field if field is not None else self.get_bingo_field(uuid)
        except NotImplementedError:
            return  # Gamemode doesn't support bingo fields

        await self.send(bingo(target_field), uuid)

    async def broadcast_bingo_field(self):
        for player_uuid in self.game_controller.players:
            await self.send_bingo_field(player_uuid)

    # --- Hooks for subclasses ---
    def get_item_pool(self, uuid):
        raise NotImplementedError

    def add_item_to_pool(self, uuid, new_item):
        raise NotImplementedError

    async def broadcast_item_list(self, uuid):
        await self.send(item_list(self.get_item_pool(uuid)), uuid)

    # --- Internal helpers ---
    async def _add_item_and_notify(self, uuid, pair_id, new_item, cached):
        self.add_item_to_pool(uuid, new_item)
        await self.send(pair_result(pair_id, new_item, not cached), uuid)
        await self.broadcast_item_list(uuid)

    async def _send_state(self, uuid):
        await self.send(clear(), uuid)
        await self.send(gamemode(self.mode_name), uuid)
        await self.send(username(self.get_player_name(uuid)), uuid)
        await self.broadcast_item_list(uuid)
        await self.send_bingo_field(uuid)
        await self.send(news(""), uuid)

    async def _send_state_to_all(self):
        for uuid in self.game_controller.players:
            await self._send_state(uuid)

    async def send(self, data, uuid=None):
        if uuid:
            await self.game_controller.send_to_uuid(uuid, data)
        else:
            await self.game_controller.send_to_all(data)

    def get_player_name(self, uuid):
        return self.game_controller.get_player_name(uuid) or 'Unbekannt'