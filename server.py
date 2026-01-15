import logging
import os
from typing import Any, Dict

import socketio
from aiohttp import web

from game import GameController
from templates import error

log = logging.getLogger('webserver')

NAMESPACE = '/game'


class GameNamespace(socketio.AsyncNamespace):
    def __init__(self, controller: GameController):
        super().__init__(NAMESPACE)
        self.controller = controller
        self.sid_user = {}
        self.sid_name = {}

    async def on_connect(self, sid: str, environ: Dict[str, Any]):
        user_id, display_name = self._extract_identity(environ)
        if not user_id:
            log.warning('Connection %s missing user id header, disconnecting', sid)
            await self.emit('server_message', error('Missing user identity'), to=sid, namespace=self.namespace)
            return await self.disconnect(sid)
        self.sid_user[sid] = user_id
        self.sid_name[sid] = display_name
        log.info('Client connected: %s as %s (%s)', sid, user_id, display_name)

    async def on_join(self, sid: str, data: Dict[str, Any]):
        log.debug('Join request from %s: %s', sid, data)
        if not isinstance(data, dict):
            await self.emit('server_message', error('Malformed join payload'), to=sid, namespace=self.namespace)
            return await self.disconnect(sid)

        uuid = self.sid_user.get(sid)
        name = self.sid_name.get(sid)

        if not uuid:
            await self.emit('server_message', error('Missing user identity'), to=sid, namespace=self.namespace)
            return await self.disconnect(sid)

        if not name:
            name = 'Unbekannt'

        await self.controller.handle_client_join(sid, uuid, name)

    async def on_pair(self, sid: str, data: Dict[str, Any]):
        uuid = self.controller.sid_to_uuid.get(sid)
        if not uuid:
            return await self.emit('server_message', error('Not joined'), to=sid, namespace=self.namespace)

        if not isinstance(data, dict) or 'pair' not in data or 'id' not in data:
            return await self.emit('server_message', error('Invalid pair payload'), to=sid, namespace=self.namespace)

        pair_id = data.get('id')
        if not isinstance(pair_id, int):
            return await self.emit('server_message', error('Invalid pair id'), to=sid, namespace=self.namespace)

        pair = data.get('pair')
        if not isinstance(pair, list) or len(pair) != 2:
            return await self.emit('server_message', error('Pair must contain two items'), to=sid, namespace=self.namespace)

        await self.controller.handle_client_pair(uuid, pair_id, pair[0], pair[1])

    async def on_bingo_click(self, sid: str, data: Dict[str, Any]):
        uuid = self.controller.sid_to_uuid.get(sid)
        if not uuid:
            return await self.emit('server_message', error('Not joined'), to=sid, namespace=self.namespace)

        if not isinstance(data, dict):
            return await self.emit('server_message', error('Invalid bingo payload'), to=sid, namespace=self.namespace)

        index = data.get('index')
        row = data.get('row')
        col = data.get('col')
        size = data.get('size')

        if not all(isinstance(val, int) for val in (index, row, col, size)):
            return await self.emit('server_message', error('Invalid bingo coordinates'), to=sid, namespace=self.namespace)

        click_data = {
            'index': index,
            'row': row,
            'col': col,
            'size': size,
            'text': data.get('text') if isinstance(data.get('text'), str) else '',
            'done': bool(data.get('done')),
            'done_color': data.get('done_color') if isinstance(data.get('done_color'), str) else None,
        }

        await self.controller.handle_client_bingo_click(uuid, click_data)

    async def on_username(self, sid: str, data: Dict[str, Any]):
        # Usernames are managed by OAuth2; ignore client-side rename attempts
        return await self.emit('server_message', error('Username managed by SSO'), to=sid, namespace=self.namespace)

    async def on_disconnect(self, sid: str):
        await self.controller.handle_disconnect(sid)
        self.sid_user.pop(sid, None)
        self.sid_name.pop(sid, None)
        log.info('Client disconnected: %s', sid)

    def _extract_identity(self, environ: Dict[str, Any]):
        request = environ.get('aiohttp.request')
        if not request:
            return '', ''

        headers = request.headers

        def first(*names):
            for name in names:
                val = headers.get(name)
                if val:
                    return val
            return ''

        user_id = first(
            os.getenv('OAUTH_USER_HEADER', 'X-Auth-Request-Preferred-Username'),
            'X-Auth-Request-Preferred-Username',
            'X-Forwarded-Preferred-Username',
            'X-Auth-Request-User',
            'X-Forwarded-User',
            'X-User',
        )

        display_name = first(
            'X-Auth-Request-Preferred-Username',
            'X-Forwarded-Preferred-Username',
            'X-Auth-Request-User',
            'X-Forwarded-User',
            'X-User',
            'X-Auth-Request-Email',
            'X-Forwarded-Email',
            'X-Email',
        )

        if not display_name:
            display_name = user_id

        return user_id, display_name


class GameServer:
    def __init__(self):
        self.socket_server = socketio.AsyncServer(
            async_mode='aiohttp',
            cors_allowed_origins='*',
            logger=True,
            engineio_logger=logging.getLogger('engineio.server'),
        )
        self.app = web.Application()
        self.socket_server.attach(self.app)
        self.controller = GameController(self.socket_server, namespace=NAMESPACE)
        self.socket_server.register_namespace(GameNamespace(self.controller))
        self._setup_static_routes()
        self._setup_admin_routes()

    def _setup_static_routes(self):
        # Serve frontend assets from the ui folder at the project root
        static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ui')
        if not os.path.isdir(static_dir):
            log.warning('Static directory not found: %s', static_dir)
            return

        # Explicit index route to serve the main page
        async def index_handler(_: web.Request):
            return web.FileResponse(os.path.join(static_dir, 'index.html'))

        self.app.router.add_get('/', index_handler)
        # Static files (JS/CSS/assets) served from root paths
        self.app.router.add_static('/', static_dir, show_index=False)

    def _setup_admin_routes(self):
        token = os.getenv('ADMIN_TOKEN')

        async def _require_admin(request: web.Request):
            if not token:
                return None

            header = request.headers.get('Authorization', '')
            bearer = header.removeprefix('Bearer ').strip() if isinstance(header, str) else ''
            if bearer == token:
                return None
            return web.json_response({'error': 'unauthorized'}, status=401)

        async def admin_status(request: web.Request):
            unauthorized = await _require_admin(request)
            if unauthorized:
                return unauthorized

            return web.json_response({
                'gamemode': self.controller.get_gamemode_name(),
                'users': self.controller.list_users(),
            })

        async def admin_users(request: web.Request):
            unauthorized = await _require_admin(request)
            if unauthorized:
                return unauthorized

            return web.json_response({'users': self.controller.list_users()})

        async def admin_gamemode(request: web.Request):
            unauthorized = await _require_admin(request)
            if unauthorized:
                return unauthorized

            try:
                body = await request.json()
            except Exception:
                return web.json_response({'error': 'invalid json body'}, status=400)

            mode = body.get('mode') if isinstance(body, dict) else None
            config = body.get('config')
            if not isinstance(mode, str):
                return web.json_response({'error': 'mode must be a string'}, status=400)

            try:
                new_mode = await self.controller.switch_gamemode(mode, config)
            except ValueError as exc:
                return web.json_response({'error': str(exc)}, status=400)

            return web.json_response({
                'gamemode': new_mode,
                'users': self.controller.list_users(),
            })

        async def admin_broadcast(request: web.Request):
            unauthorized = await _require_admin(request)
            if unauthorized:
                return unauthorized

            try:
                body = await request.json()
            except Exception:
                return web.json_response({'error': 'invalid json body'}, status=400)

            message = body.get('message')
            if not isinstance(message, str) or not message.strip():
                 return web.json_response({'error': 'message must be a non-empty string'}, status=400)
            
            await self.controller.broadcast(message)
            return web.json_response({'status': 'ok'})

        self.app.router.add_get('/admin/status', admin_status)
        self.app.router.add_get('/admin/users', admin_users)
        self.app.router.add_post('/admin/gamemode', admin_gamemode)
        self.app.router.add_post('/admin/broadcast', admin_broadcast)

    def run(self):
        port = int(os.getenv('PORT', '8080'))
        logging.getLogger('aiohttp.web').setLevel(logging.WARNING)
        logging.getLogger('aiohttp.access').setLevel(logging.WARNING)
        web.run_app(self.app, port=port)


def start_server():
    server = GameServer()
    server.run()
