import atexit
import logging
import json

from cache import Cache
from gamemodes.classic import ClassicGamemode
from templates import username
import os
import httpx
import regex
import asyncio

log = logging.getLogger('GameController')
CACHE_FILE = 'cache/cache.json'


class GameController:
    
    def __init__(self):
        self.players = {}
        self.gamemode = ClassicGamemode(self)
        self.cache = Cache()
        
        log.info('Loading cache')
        self.cache.load(CACHE_FILE)
        atexit.register(self.save_cache)
        atexit.register(self.disconnect_all)
        pass

    def disconnect_all(self):
        log.info('Disconnecting all clients')
        for player in self.players:
            self.players[player]['ws'].close()
        pass

    def save_cache(self):
        log.info('Saving cache')
        self.cache.save(CACHE_FILE)
    
    async def send_to_all(self, data):
        for player in self.players:
            log.debug('Sending to ' + player)
            await self.players[player]['ws'].send_json(data)
        pass
    
    async def send_to_uuid(self, uuid, data):
        await self.players[uuid]['ws'].send_json(data)
        pass
    
    async def handle_client_message(self, uuid, data):
        if not data.get('type'):
            log.error('Recieved client message without type')
            return
        
        if data.get('type') == 'pair':
            if data.get('pair') and data.get('id') is not None and len(data.get('pair')) == 2:
                # pair is a array of length 2
                item1 = data.get('pair')[0]
                item2 = data.get('pair')[1]
                pair_id = data.get('id')
                await self.handle_client_pair(uuid, pair_id, item1, item2)
            else:
                log.error('Recieved client message with invalid pair')
            pass
        elif data.get('type') == 'username':
            if data.get('username'):
                self.handle_client_username(uuid, data.get('username'))
            else:
                log.error('Recieved client message with invalid username')
            pass
        else:
            log.error('Recieved client message with invalid type')
            return
        pass
    
    async def handle_client_pair(self, uuid, pair_id, item1, item2):
        await self.gamemode.pair(uuid, pair_id, item1, item2)
        pass
    
    def handle_client_username(self, uuid, username):
        self.gamemode.username(uuid, username)
        pass
    
    async def handle_client_join(self, uuid, name, ws):
        if uuid in self.players:
            log.info('Client with uuid ' + uuid + ' joined twice, disconnecting old connection')
            await self.players[uuid]['ws'].close()
            self.players[uuid] = {'name': name, 'ws': ws}
            await self.gamemode.rejoin(uuid)
        self.players[uuid] = {'name': name, 'ws': ws}
        await self.gamemode.join(uuid)
        pass
    
    def handle_client_disconnect(self, uuid):
        del self.players[uuid]
        pass
    
    def get_pass(self):
        return os.getenv('GAME_PASS', 'secret_password')
    
    async def set_gamemode(self, _gamemode):
        if self.gamemode:
            await self.gamemode.stop()
        self.gamemode = _gamemode
        await self.gamemode.start()
        pass
    
    def change_username(self, uuid, name):
        self.players[uuid]['name'] = name
        self.players[uuid]['ws'].send_json(username(name))
        pass
    
    async def request_combo(self, uuid, pair_id, item1, item2):
        # sort item1 and item2
        log.info('Requesting combo for ' + item1 + ' and ' + item2)
        if item1 > item2:
            item1, item2 = item2, item1
        cached = self.get_cached_combo(item1, item2)
        if cached:
            await self.gamemode.handle_combo(uuid, pair_id, item1, item2, cached, True)
        else:
            await self.ask_llm(uuid, pair_id, item1, item2)
    
    def get_cached_combo(self, item1, item2):
        return self.cache.get(item1 + item2)
    
    def cache_combo(self, item1, item2, result_name, result_emoji):
        self.cache.addPair(item1 + item2, result_name)
        self.cache.addItem(result_name, result_emoji)
        self.save_cache()
        pass
    
    async def ask_llm(self, uuid, pair_id, item1, item2):
        log.info('Asking LLM for combo of ' + item1 + ' and ' + item2)
        ollama_url = os.getenv("OLLAMA_API_URL")
        ollama_model = os.getenv("OLLAMA_MODEL") or "gemma3:12b"

        if not ollama_url:
            log.error("OLLAMA_API_URL environment variable not set")
            return

        system_prompt = (
            "You are an expert game designer for a creative combination game inspired by 'Infinite Craft'. "
            "Players combine elements like Air, Earth, Fire, and Water to create new elements. "
            "Each combination results in a new or existing element, or 'None' if it's impossible."
            "*** IMPORTANT ***"
            "NEVER output more than 1 element at a time."
            "Be creative but still logically correct!"
            "Sometimes the user will combine two of the same element. In some cases the output should be a bigger version of the element. "
            "For example, combining Water and Water might give us Ocean.\n"
            "Outputting '[Element1], [Element2]' as an element is not appropriate. Please provide a creative and logically correct response."
            "Air and Fire should not be equal to Lava."
            "Air and Stone should be Sand. As the air would erode the stone."
            "Sand and Stone should not be Beach but rather Sandstone."
            "Sand and Mud should be Clay."
            "*** VERY IMPORTANT ***"
            "PLEASE avoid outputting esoteric or nonsensical responses such as Molten Gypsum Glass Concrete!"
            "Please use spaces between words and you MUST NOT use CamelCase or snake_case."
            "Don't just combine words of the two elements. Try to combine the elements in a way that makes sense."
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
            "model": ollama_model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
        }

        log.debug(f"Payload {payload}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{ollama_url}/api/generate", json=payload)

            # --- Check HTTP response ---
            if response.status_code != 200:
                log.error(f"Ollama request failed: {response.status_code} {response.text}")
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

            responseobj.get("response")
            if not isinstance(responseobj.get("response"), str):
                log.error(f"Missing or invalid 'response' field: {responseobj}")
                return await self.gamemode.handle_combo(uuid, pair_id, item1, item2, None, False)

            # response from the llm maybe look like ```json\n{\n"name": "Steam",\n"emoji": "💨"\n}\n``` or just like {"name": "Steam", "emoji": "💨"} handle both cases
            llm_response = responseobj.get("response").strip()
            if llm_response.startswith("```") and llm_response.endswith("```"):
                llm_response = llm_response[llm_response.find('\n')+1:llm_response.rfind('```')].strip()
            try:
                result = json.loads(llm_response)
            except Exception as e:
                log.error(f"Response 'response' field is not valid JSON: {e}, body: {llm_response!r}")
                return await self.gamemode.handle_combo(uuid, pair_id, item1, item2, None, False)

            if not isinstance(result, dict):
                log.error(f"Response 'response' field is not a JSON object: {result}")
                return await self.gamemode.handle_combo(uuid, pair_id, item1, item2, None, False)

            name = result.get("name")
            emoji = result.get("emoji")

            log.debug(f"Ollama returned: name={name!r}, emoji={emoji!r}")

            def is_single_emoji(s: str) -> bool:
                # Grapheme cluster check
                return isinstance(s, str) and regex.fullmatch(r"\X", s) and len(s) <= 3

            if isinstance(name, str) and 1 <= len(name) <= 40 and is_single_emoji(emoji):
                self.cache_combo(item1, item2, name, emoji)
                await self.gamemode.handle_combo(uuid, pair_id, item1, item2, result, False)
            else:
                log.error(f"Malformed result from Ollama: {result}")
                await self.gamemode.handle_combo(uuid, pair_id, item1, item2, None, False)

        except httpx.RequestError as e:
            log.error(f"Network error requesting Ollama: {e}")
        await self.gamemode.handle_combo(uuid, pair_id, item1, item2, None, False)
        return None