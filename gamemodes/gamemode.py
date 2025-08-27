import logging
import random

from templates import *

log = logging.getLogger('BasicGamemode')


class BasicGamemode:

    def __init__(self,game_controller):
        self.game_controller = game_controller
        pass

    async def start(self):
        log.info('Game started')
        # Start the game/round
        pass

    async def end(self):
        log.info('Game ended')
        # End the game/round and show the results
        pass

    async def stop(self):
        log.info('Game stopped')
        # Stop the game/round
        pass

    async def rejoin(self, uuid):
        log.info(self.getName(uuid) + ' rejoined')
        await self.join(uuid)

    async def join(self, uuid):
        log.info(self.getName(uuid) + ' joined')
        # A player joined the game
        await self.send(item_list([
            item("Warten...","⏳"),
            ]),uuid)
        await self.send(news("+++ Bisher wurde noch kein Spielmodus ausgewählt +++ Open-Infinite nutzt JavaScript, HTML, TailwindCSS, Python, Websockets und ein Large Language Model (LLM) +++"),uuid)
        await self.send(gamemode("Lobby-Modus"),uuid)
        await self.send(username(self.getName(uuid)),uuid)
        pass

    async def pair(self, uuid,pair_id, item1, item2):
        log.info(self.getName(uuid) + ' paired ' + item1 + ' with ' + item2)
        items = [
            item("Dings","😂"),
            item("Gedöns","🤔"),
            item("Kram","🤷"),
            item("Zeug","🤨"),
                 ]
        await self.send(pair_result(pair_id,random.choice(items)),uuid)
        pass

    def handle_combo(self, uuid, pair_id, item1, item2, result, cached):
        if result is None:
            self.send(pair_empty_result(pair_id),uuid)
        else:
            self.send(pair_result(pair_id,item(result.name,result.emoji),not cached),uuid)
        pass

    def username(self, uuid, username):
        log.info(uuid + ' changed username from '+self.getName(uuid)+' to ' + username)
        self.game_controller.change_name(uuid, username)

    async def send(self, data, uuid = None):
        if uuid:
            log.info('Sending to ' + self.getName(uuid) + ': ' + str(data))
            await self.game_controller.send_to_uuid(uuid, data)
        else:
            await self.game_controller.send_to_all(data)

    def getName(self, uuid):
        return self.game_controller.players[uuid]['name']