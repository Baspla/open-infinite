import atexit
import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional

import httpx
import regex

from cache import Cache
from gamemodes.classic import ClassicGamemode
from gamemodes.gamemode import AbstractGamemode
from gamemodes.shared import SharedGamemode
from templates import username

log = logging.getLogger('GameController')
COMBO_CACHE_FILE = 'cache/combocache.json'
ITEM_CACHE_FILE = 'cache/itemcache.json'


@dataclass
class Player:
    uuid: str
    name: str
    sid: str


class GameController:
    """Coordinates players, gamemode logic, and outbound messages."""

    def __init__(self, socket_server, namespace: str = '/game'):
        self.socket_server = socket_server
        self.namespace = namespace
        self.players: Dict[str, Player] = {}
        self.sid_to_uuid: Dict[str, str] = {}

        env_gamemode = os.getenv('GAME_MODE', 'classic').lower()
        if env_gamemode == 'classic':
            log.info('Starting in Classic Gamemode')
            self.gamemode: AbstractGamemode = ClassicGamemode(self)
        elif env_gamemode == 'shared':
            log.info('Starting in Shared Gamemode')
            self.gamemode = SharedGamemode(self)
        else:
            log.info('Unknown GAME_MODE %s, falling back to Classic Gamemode', env_gamemode)
            self.gamemode = ClassicGamemode(self)

        self.cache = Cache(COMBO_CACHE_FILE, ITEM_CACHE_FILE)
        log.info('Loading cache')
        self.cache.load()
        atexit.register(self.save_cache)
        atexit.register(self.disconnect_all)

    def disconnect_all(self):
        log.info('Disconnecting all clients')
        async def _disconnect():
            for player in list(self.players.values()):
                await self.socket_server.disconnect(player.sid, namespace=self.namespace)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_disconnect())
        except RuntimeError:
            asyncio.run(_disconnect())

    def save_cache(self):
        log.info('Saving cache')
        self.cache.save()
    
    async def send_to_all(self, data):
        """Broadcast a message to every connected player."""
        log.debug('Broadcasting payload: %s', data)
        await self.socket_server.emit('server_message', data, namespace=self.namespace)

    async def send_to_uuid(self, uuid: str, data):
        player = self.players.get(uuid)
        if not player:
            log.warning('Attempted to send to unknown player %s', uuid)
            return
        log.debug('Sending to %s: %s', uuid, data)
        await self.socket_server.emit('server_message', data, namespace=self.namespace, to=player.sid)
    
    async def handle_client_pair(self, uuid: str, pair_id: int, item1: str, item2: str):
        await self.gamemode.pair(uuid, pair_id, item1, item2)

    async def handle_client_username(self, uuid: str, new_username: str):
        # Usernames are managed by SSO; ignore client requests
        return

    async def handle_client_bingo_click(self, uuid: str, click_data):
        await self.gamemode.handle_bingo_click(uuid, click_data)

    async def handle_client_join(self, sid: str, uuid: str, name: str):
        existing_player = self.players.get(uuid)
        if existing_player:
            log.info('Client with uuid %s reconnected, dropping old connection', uuid)
            await self.socket_server.disconnect(existing_player.sid, namespace=self.namespace)
        player = Player(uuid=uuid, name=name, sid=sid)
        self.players[uuid] = player
        self.sid_to_uuid[sid] = uuid
        await self.gamemode.join(uuid)

    async def handle_disconnect(self, sid: str):
        uuid = self.sid_to_uuid.pop(sid, None)
        if not uuid:
            return
        if uuid in self.players:
            del self.players[uuid]
            log.info('Client %s disconnected', uuid)

    async def set_gamemode(self, _gamemode: AbstractGamemode):
        if self.gamemode:
            await self.gamemode.stop()
        self.gamemode = _gamemode
        await self.gamemode.start()

    def get_player_name(self, uuid: str) -> Optional[str]:
        player = self.players.get(uuid)
        return player.name if player else None
    
    async def request_combo(self, uuid, pair_id, item1, item2):
        log.info('Requesting combo for %s and %s', item1, item2)
        cached = self.cache.get_combo(item1, item2)
        if cached:
            if not cached.get('emoji') and isinstance(cached.get('name'), str):
                emoji = await self.ask_llm_for_emoji(cached['name'])
                if emoji:
                    cached['emoji'] = emoji
                    self.cache.set_item_emoji(cached['name'], emoji)
                    self.save_cache()
            await self.gamemode.handle_combo(uuid, pair_id, item1, item2, cached, True)
        else:
            await self.ask_llm(uuid, pair_id, item1, item2)
    
    
    def _is_single_emoji(self, s: str) -> bool:
        # Grapheme cluster check to keep single emoji outputs
        return isinstance(s, str) and regex.fullmatch(r"\X", s) is not None and len(s) <= 3

    async def ask_llm_for_emoji(self, item_name: str) -> Optional[str]:
        log.info('Requesting emoji for %s', item_name)
        llm_url = os.getenv("LLM_API_URL") or "https://openrouter.ai/api/v1/chat/completions"
        llm_model = os.getenv("LLM_MODEL") or "openrouter/auto"
        llm_key = os.getenv("LLM_KEY")

        if not llm_key:
            log.error("LLM_KEY environment variable not set")
            return None
        if not llm_url:
            log.error("LLM_API_URL environment variable not set")
            return None

        system_prompt = (
            "You pick a single emoji that best represents a given item name. "
            "Use common, recognizable emoji only. Respond only with a JSON object containing the key 'emoji'."
        )
        user_prompt = (
            f"Provide one emoji that represents '{item_name}'. "
            "Return only a JSON object with key 'emoji' and no extra text."
        )
        payload = {
            "model": llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "stream": False,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    llm_url,
                    json=payload,
                    timeout=30.0,
                    headers={"Authorization": f"Bearer {llm_key}"},
                )

            if response.status_code != 200:
                log.error(f"Emoji LLM request failed: {response.status_code} {response.text}")
                return None

            try:
                responseobj = response.json()
            except Exception as e:
                log.error(f"Emoji response is not valid JSON: {e}, body: {response.text[:200]!r}")
                return None

            if not isinstance(responseobj, dict):
                log.error(f"Unexpected emoji JSON structure: {responseobj}")
                return None

            choices = responseobj.get("choices")
            if not isinstance(choices, list) or not choices:
                log.error(f"Missing or invalid 'choices' field for emoji request: {responseobj}")
                return None

            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            llm_response = message.get("content") if isinstance(message, dict) else None
            if not isinstance(llm_response, str):
                log.error(f"Missing or invalid emoji message content: {responseobj}")
                return None

            llm_response = llm_response.strip()
            if llm_response.startswith("```") and llm_response.endswith("```"):
                llm_response = llm_response[llm_response.find('\n')+1:llm_response.rfind("```")].strip()

            try:
                result = json.loads(llm_response)
            except Exception as e:
                log.error(f"Emoji message content is not valid JSON: {e}, body: {llm_response!r}")
                return None

            if not isinstance(result, dict):
                log.error(f"Emoji message content is not a JSON object: {result}")
                return None

            emoji = result.get("emoji")
            if emoji and self._is_single_emoji(emoji):
                log.debug(f"Emoji LLM returned {emoji!r} for {item_name!r}")
                return emoji

            log.error(f"Emoji result malformed for {item_name!r}: {result}")
            return None
        except httpx.RequestError as e:
            log.error(f"Network error requesting emoji LLM: {e}")
        return None

    async def ask_llm(self, uuid, pair_id, item1, item2):
        log.info('Asking LLM for combo of %s and %s', item1, item2)
        llm_url = os.getenv("LLM_API_URL") or "https://openrouter.ai/api/v1/chat/completions"
        llm_model = os.getenv("LLM_MODEL") or "openrouter/auto"
        llm_key = os.getenv("LLM_KEY")

        if not llm_key:
            log.error("LLM_KEY environment variable not set")
            return await self.gamemode.handle_combo(uuid, pair_id, item1, item2, None, False)
        if not llm_url:
            log.error("LLM_API_URL environment variable not set")
            return await self.gamemode.handle_combo(uuid, pair_id, item1, item2, None, False)

        system_prompt = (
            "You are an expert game designer for a creative combination game. "
            "Players combine elements like Air, Earth, Fire, and Water to create new elements. "
            "Each combination results in a new or existing element, or 'None' if it's impossible."
            "*** IMPORTANT ***"
            "NEVER output more than 1 element at a time."
            "Be creative but still logically correct!"
            "Sometimes the user will combine two of the same element. In some cases the output should be a bigger version of the element or just the same element again."
            "For example, combining Water and Water might give us Ocean.\n"
            "Don't just add bigger adjectives like 'Big', 'Mega' or 'Infinite' to the element name. Instead, think of a logical larger version of the element."
            "Outputting '[Element1], [Element2]' as an element is not appropriate. Please provide a creative and logically correct response."
            "Air and Fire should not be equal to Lava."
            "Air and Stone should be Sand. As the air would erode the stone."
            "Sand and Stone should not be Beach but rather Sandstone."
            "Sand and Mud should be Clay."
            "*** VERY IMPORTANT ***"
            "PLEASE avoid outputting esoteric or nonsensical responses such as Molten Gypsum Glass Concrete!"
            "Please use spaces between words and you MUST NOT use CamelCase or snake_case."
            "Don't just combine words of the two elements. Try to combine the elements in a way that makes sense."
            "If the two elements cannot logically be combined or are too nonsensical, respond with None."
            "Use a single relevant emoji to represent the resulting element."
            "Don't use emoji in the element name. Only use emoji in the emoji field."
            "When given two items, invent a new item that could logically result from combining them. "
            "Respond concisely with a JSON object containing 'name' (the new item's name, less than 30 characters) and 'emoji' (a single relevant emoji, not text)."
        )
        user_prompt = (
            f"Combine '{item1}' and '{item2}' into a new item. "
            "Return only a JSON object with 'name' (shorter than 30 characters) and 'emoji' (a single emoji)."
        )
        payload = {
            "model": llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "stream": False,
        }

        log.debug(f"Payload {payload}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    llm_url,
                    json=payload,
                    timeout=30.0,
                    headers={"Authorization": f"Bearer {llm_key}"},
                )

            # --- Check HTTP response ---
            if response.status_code != 200:
                log.error(f"LLM request failed: {response.status_code} {response.text}")
                return await self.gamemode.handle_combo(uuid, pair_id, item1, item2, None, False)

            # --- Try parsing JSON ---
            try:
                responseobj = response.json()
            except Exception as e:
                log.error(f"Response is not valid JSON: {e}, body: {response.text[:200]!r}")
                return await self.gamemode.handle_combo(uuid, pair_id, item1, item2, None, False)

            # --- Validate result ---
            if not isinstance(responseobj, dict):
                log.error(f"Unexpected JSON structure: {responseobj}")
                return await self.gamemode.handle_combo(uuid, pair_id, item1, item2, None, False)

            choices = responseobj.get("choices")
            if not isinstance(choices, list) or not choices:
                log.error(f"Missing or invalid 'choices' field: {responseobj}")
                return await self.gamemode.handle_combo(uuid, pair_id, item1, item2, None, False)

            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            llm_response = message.get("content") if isinstance(message, dict) else None
            if not isinstance(llm_response, str):
                log.error(f"Missing or invalid message content: {responseobj}")
                return await self.gamemode.handle_combo(uuid, pair_id, item1, item2, None, False)

            # Response may be wrapped in fenced code blocks
            llm_response = llm_response.strip()
            if llm_response.startswith("```") and llm_response.endswith("```"):
                llm_response = llm_response[llm_response.find('\n')+1:llm_response.rfind('```')].strip()
            try:
                result = json.loads(llm_response)
            except Exception as e:
                log.error(f"LLM message content is not valid JSON: {e}, body: {llm_response!r}")
                return await self.gamemode.handle_combo(uuid, pair_id, item1, item2, None, False)

            if not isinstance(result, dict):
                log.error(f"LLM message content is not a JSON object: {result}")
                return await self.gamemode.handle_combo(uuid, pair_id, item1, item2, None, False)

            name = result.get("name")
            emoji = result.get("emoji")
            cached_emoji = self.cache.get_item_emoji(name) if isinstance(name, str) else None
            final_emoji = cached_emoji or emoji

            log.debug(f"LLM returned: name={name!r}, emoji={emoji!r}")

            if isinstance(name, str) and 1 <= len(name) <= 40 and isinstance(final_emoji, str) and self._is_single_emoji(final_emoji):
                normalized_result = {"name": name, "emoji": final_emoji}
                self.cache.add_combo(item1, item2, name, final_emoji)
                self.save_cache()
                return await self.gamemode.handle_combo(uuid, pair_id, item1, item2, normalized_result, False)
            else:
                log.error(f"Malformed result from LLM: {result}")
                return await self.gamemode.handle_combo(uuid, pair_id, item1, item2, None, False)

        except httpx.RequestError as e:
            log.error(f"Network error requesting LLM: {e}")
        return await self.gamemode.handle_combo(uuid, pair_id, item1, item2, None, False)