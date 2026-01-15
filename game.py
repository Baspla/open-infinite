import atexit
import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional, Any, Tuple

import httpx
import regex

from cache import Cache
from gamemodes.classic import ClassicGamemode
from gamemodes.gamemode import AbstractGamemode
from gamemodes.shared import SharedGamemode
from gamemodes.bingo import BingoGamemode
from templates import username, users, news
import random

log = logging.getLogger('GameController')
COMBO_CACHE_FILE = 'cache/combocache.json'
ITEM_CACHE_FILE = 'cache/itemcache.json'


@dataclass
class Player:
    uuid: str
    name: str
    sid: str
    color: Optional[str] = None


class GameController:
    """Coordinates players, gamemode logic, and outbound messages."""

    def __init__(self, socket_server, namespace: str = '/game'):
        self.socket_server = socket_server
        self.namespace = namespace
        self.players: Dict[str, Player] = {}
        self.sid_to_uuid: Dict[str, str] = {}
        self.available_colors = ["#EF4444", "#3B82F6", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899", "#14B8A6", "#84CC16"]
        self.assigned_colors = {} # uuid -> color

        env_gamemode = os.getenv('GAME_MODE', 'classic').lower()
        if env_gamemode == 'classic':
            log.info('Starting in Classic Gamemode')
            self.gamemode: AbstractGamemode = ClassicGamemode(self)
        elif env_gamemode == 'shared':
            log.info('Starting in Shared Gamemode')
            self.gamemode = SharedGamemode(self)
        elif env_gamemode == 'bingo':
            log.info('Starting in Bingo Gamemode')
            self.gamemode = BingoGamemode(self)
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

    async def broadcast(self, message: str):
         await self.send_to_all(news(message))

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
        
        # Assign color
        if uuid in self.assigned_colors:
            color = self.assigned_colors[uuid]
        else:
            if self.available_colors:
                color = self.available_colors.pop(0)
            else:
                 color = "#{:06x}".format(random.randint(0, 0xFFFFFF))
            self.assigned_colors[uuid] = color

        player = Player(uuid=uuid, name=name, sid=sid, color=color)
        self.players[uuid] = player
        self.sid_to_uuid[sid] = uuid
        await self.gamemode.join(uuid)
        await self.broadcast_user_list()

    async def handle_disconnect(self, sid: str):
        uuid = self.sid_to_uuid.pop(sid, None)
        if not uuid:
            return
        if uuid in self.players and self.players[uuid].sid == sid:
            # We keep the color assigned in self.assigned_colors so if they reconnect they get same color
            del self.players[uuid]
            log.info('Client %s disconnected', uuid)
            await self.broadcast_user_list()

    async def broadcast_user_list(self):
        user_list = [
            {"name": p.name, "color": p.color, "uuid": p.uuid} 
            for p in self.players.values()
        ]
        await self.send_to_all(users(user_list))

    async def set_gamemode(self, _gamemode: AbstractGamemode):
        if self.gamemode:
            await self.gamemode.stop()
        self.gamemode = _gamemode
        await self.gamemode.start()

    def list_users(self):
        return [
            {"uuid": player.uuid, "name": player.name}
            for player in self.players.values()
        ]

    def get_gamemode_name(self) -> Optional[str]:
        return self.gamemode.mode_name if self.gamemode else None

    async def switch_gamemode(self, mode_name: str, config: Optional[Dict[str, Any]] = None) -> str:
        normalized = (mode_name or '').strip().lower()
        config = config or {}

        if normalized == 'classic':
            new_mode = ClassicGamemode(self)
        elif normalized == 'shared':
            new_mode = SharedGamemode(self)
        elif normalized == 'bingo':
            new_mode = BingoGamemode(self, config)
        else:
            raise ValueError(f"Unsupported gamemode '{mode_name}'")

        await self.set_gamemode(new_mode)
        return new_mode.mode_name

    def get_player_name(self, uuid: str) -> Optional[str]:
        player = self.players.get(uuid)
        return player.name if player else None
    
    async def request_combo(self, uuid, pair_id, item1, item2):
        log.info('Requesting combo for %s and %s', item1, item2)
        cached: Optional[Dict[str, Any]] = self.cache.get_combo(item1, item2)
        if cached:
            name = cached.get('name')
            if name is None:
                await self.gamemode.handle_combo(uuid, pair_id, item1, item2, None, True)
                return

            cached_emoji = self._valid_single_emoji(cached.get('emoji'))
            cached['emoji'] = cached_emoji if cached_emoji is not None else None

            if cached_emoji is None and isinstance(name, str):
                emoji_value, persist = await self.ask_llm_for_emoji(name)
                if emoji_value is not None:
                    cached['emoji'] = emoji_value
                if persist and emoji_value:
                    self.cache.set_item_emoji(name, emoji_value)
                    self.save_cache()
            await self.gamemode.handle_combo(uuid, pair_id, item1, item2, cached, True)
        else:
            await self.ask_llm(uuid, pair_id, item1, item2)
    
    
    def _is_single_emoji(self, s: str) -> bool:
        # Grapheme cluster check to keep single emoji outputs
        return isinstance(s, str) and regex.fullmatch(r"\X", s) is not None and len(s) <= 3

    def _normalize_emoji_candidate(self, emoji: Optional[str]) -> Optional[str]:
        if not isinstance(emoji, str):
            return None
        cleaned = emoji.strip()
        return cleaned or None

    def _valid_single_emoji(self, emoji: Optional[str]) -> Optional[str]:
        cleaned = self._normalize_emoji_candidate(emoji)
        if cleaned and self._is_single_emoji(cleaned):
            return cleaned
        return None

    async def ask_llm_for_emoji(self, item_name: str) -> Tuple[Optional[str], bool]:
        log.info('Requesting emoji for %s', item_name)
        llm_url = os.getenv("LLM_API_URL") or "https://openrouter.ai/api/v1/chat/completions"
        llm_model = os.getenv("LLM_MODEL") or "openrouter/auto"
        llm_key = os.getenv("LLM_KEY")

        if not llm_key:
            log.error("LLM_KEY environment variable not set")
            return None, False
        if not llm_url:
            log.error("LLM_API_URL environment variable not set")
            return None, False

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
                return None, False

            try:
                responseobj = response.json()
            except Exception as e:
                log.error(f"Emoji response is not valid JSON: {e}, body: {response.text[:200]!r}")
                return None, False

            if not isinstance(responseobj, dict):
                log.error(f"Unexpected emoji JSON structure: {responseobj}")
                return None, False

            choices = responseobj.get("choices")
            if not isinstance(choices, list) or not choices:
                log.error(f"Missing or invalid 'choices' field for emoji request: {responseobj}")
                return None, False

            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            llm_response = message.get("content") if isinstance(message, dict) else None
            if not isinstance(llm_response, str):
                log.error(f"Missing or invalid emoji message content: {responseobj}")
                return None, False

            llm_response = llm_response.strip()
            if llm_response.startswith("```") and llm_response.endswith("```"):
                llm_response = llm_response[llm_response.find('\n')+1:llm_response.rfind("```")].strip()

            try:
                result = json.loads(llm_response)
            except Exception as e:
                log.error(f"Emoji message content is not valid JSON: {e}, body: {llm_response!r}")
                return None, False

            if not isinstance(result, dict):
                log.error(f"Emoji message content is not a JSON object: {result}")
                return None, False

            emoji = self._valid_single_emoji(result.get("emoji"))
            if emoji:
                log.debug(f"Emoji LLM returned {emoji!r} for {item_name!r}")
                return emoji, True

            log.error(f"Emoji result malformed for {item_name!r}: {result}")
            return "", False
        except httpx.RequestError as e:
            log.error(f"Network error requesting emoji LLM: {e}")
        return None, False

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
            "DO NOT escalate the elements to absurd levels, for example Extreme Fire, Ultra Water, Infinite Air or Eternal Earth."
            "For example, combining Water and Water might give us Ocean."
            "Don't just add bigger adjectives like 'Big', 'Double', 'Mega' or 'Infinite' to the element name. Instead, think of a logical larger version of the element."
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
            "When given two items, invent a new item that could logically result from combining them."
            "Respond concisely with a JSON object containing 'name' (the new item's name, less than 30 characters) and 'emoji' (a single relevant emoji, not text)."
        )
        user_prompt = (
            f"Combine '{item1}' and '{item2}' into a new sensible item. "
            "Return only a JSON object with 'name' (shorter than 30 characters or None) and 'emoji' (a single emoji)."
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
            stripped_name = name.strip().lower() if isinstance(name, str) else None
            if stripped_name == "none":
                name = None

            emoji_from_llm = self._valid_single_emoji(result.get("emoji"))
            cached_emoji = self._valid_single_emoji(self.cache.get_item_emoji(name)) if isinstance(name, str) else None
            final_emoji = cached_emoji or emoji_from_llm

            log.debug(f"LLM returned: name={name!r}, emoji={result.get('emoji')!r}, cached_emoji={cached_emoji!r}")

            if name is None:
                self.cache.add_combo(item1, item2, None, None)
                self.save_cache()
                return await self.gamemode.handle_combo(uuid, pair_id, item1, item2, None, False)

            if isinstance(name, str) and 1 <= len(name) <= 40:
                emoji_to_store = final_emoji
                emoji_for_user = emoji_to_store if emoji_to_store is not None else ""
                if emoji_from_llm is None and result.get("emoji"):
                    log.error(f"Malformed emoji for {name!r}, storing None: {result.get('emoji')!r}")

                self.cache.add_combo(item1, item2, name, emoji_to_store)
                self.save_cache()
                normalized_result = {"name": name, "emoji": emoji_for_user}
                return await self.gamemode.handle_combo(uuid, pair_id, item1, item2, normalized_result, False)

            log.error(f"Malformed result from LLM: {result}")
            return await self.gamemode.handle_combo(uuid, pair_id, item1, item2, None, False)

        except httpx.RequestError as e:
            log.error(f"Network error requesting LLM: {e}")
        return await self.gamemode.handle_combo(uuid, pair_id, item1, item2, None, False)