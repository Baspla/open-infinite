from math import log
import os
import json
import logging
from aiohttp import web

from game import GameController
from templates import invalid_pass, release, unauthorized

log = logging.getLogger('webserver')

game_controller: GameController

CONTROLLER_PASS = os.environ.get('CONTROLLER_PASS') or 'defaultPassword123'


async def client_handler(request):
    global game_controller
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    try:
        async for msg in ws:
            data = json.loads(msg.data)
            if data is None:
                continue
            if ws not in client_connections:
                log.info(request.remote + ' tries to join with Uuid: ' + data.get('uuid') + ', Name: ' + data.get(
                    'name') + ' and Pass: ' + data.get('pass'))
                if data.get('type') == 'join' and data.get('uuid') and data.get('name') and data.get(
                        'pass') == game_controller.get_pass():
                    uuid = data.get('uuid')
                    name = data.get('name')
                    client_connections[ws] = uuid
                    await game_controller.handle_client_join(uuid, name, ws)
                    continue
                else:
                    log.info(request.remote + ' was rejected')
                    await ws.close()
                    return ws
            await game_controller.handle_client_message(client_connections[ws], data)
            continue

    finally:
        log.debug('Client disconnected')
        if ws in client_connections:
            game_controller.handle_client_disconnect(client_connections[ws])
            del client_connections[ws]

    return ws


client_connections = {}
controller = None


def start_server(_game_controller):
    global game_controller
    game_controller = _game_controller
    app = web.Application()
    app.router.add_get('/client', client_handler)
    port = os.getenv('PORT', '8080')
    web.run_app(app, port=int(port))
    logging.getLogger('aiohttp.web').setLevel(logging.WARNING)
