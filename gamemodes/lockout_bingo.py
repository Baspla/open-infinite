import asyncio
import logging
import random
from gamemodes.classic import ClassicGamemode
from templates import bingo, news

log = logging.getLogger('LockoutBingoGamemode')

class LockoutBingoGamemode(ClassicGamemode):
    def __init__(self, game_controller, config=None):
        super().__init__(game_controller)
        config = config or {}
        self.mode_name = "Lockout Bingo"
        self.bingo_size = int(config.get('size', 5))
        self.shared_cells = [] # list of {text, done, done_color, owner_uuid}
        self.timer_seconds = int(config.get('timer', 900))
        self.custom_words = config.get('words', [])
        self.timer_active = False
        self._loop_task = None
        self._initialized = False

    async def start(self):
        await super().start()
        self._ensure_initialized()
        self._ensure_started()
        await self.broadcast_bingo_field()

    def _ensure_initialized(self):
        if self._initialized: return
        
        if self.custom_words:
            all_items = self.custom_words
        else:
            all_items = list(self.game_controller.cache.itemcache.keys())

        if not all_items:
             log.warning("Cache empty, deferring initialization")
             # We might try again? Or just empty board.
             self.shared_cells = [{"text": "?", "done": False, "done_color": None, "owner": None} for _ in range(self.bingo_size**2)]
             return # Can't init properly yet

        if len(all_items) < self.bingo_size * self.bingo_size:
             selection = all_items + ["?"] * (self.bingo_size * self.bingo_size - len(all_items))
             random.shuffle(selection)
             items = selection[:self.bingo_size * self.bingo_size]
        else:
            items = random.sample(all_items, self.bingo_size * self.bingo_size)
        
        self.shared_cells = [{"text": item, "done": False, "done_color": None, "owner": None} for item in items]
        self._initialized = True

    def _ensure_started(self):
         if not self.timer_active:
            self.timer_active = True
            if self._loop_task is None or self._loop_task.done():
                self._loop_task = asyncio.create_task(self.game_loop())

    async def game_loop(self):
        while self.timer_active and self.timer_seconds > 0:
            minutes = self.timer_seconds // 60
            seconds = self.timer_seconds % 60
            try:
                if self.timer_seconds % 60 == 0 or self.timer_seconds <= 10:
                    await self.send(news(f"Zeit: {minutes:02d}:{seconds:02d}"))
            except Exception as e:
                log.error(f"Error in game loop: {e}")
            await asyncio.sleep(1)
            self.timer_seconds -= 1
        
        if self.timer_active:
             await self.send(news("Zeit abgelaufen!"))
             await self.check_winner(final=True)
             self.timer_active = False

    async def stop(self):
        self.timer_active = False
        if self._loop_task:
            self._loop_task.cancel()
        await super().stop()

    def _get_color(self, uuid):
        player = self.game_controller.players.get(uuid)
        return player.color if player else "#000000"

    def get_bingo_field(self, uuid):
        self._ensure_initialized()
        self._ensure_started()
        return {
            "size": self.bingo_size,
            "cells": self.shared_cells
        }

    async def _add_item_and_notify(self, uuid, pair_id, new_item, cached):
        await super()._add_item_and_notify(uuid, pair_id, new_item, cached)
        await self.check_bingo_lockout(uuid, new_item.get('name'))

    async def check_bingo_lockout(self, uuid, item_name):
        changed = False
        for cell in self.shared_cells:
            if cell['text'] == item_name and not cell['done']:
                cell['done'] = True
                cell['owner'] = uuid
                cell['done_color'] = self._get_color(uuid)
                changed = True
        
        if changed:
            await self.broadcast_bingo_field()
            await self.check_winner()

    async def check_winner(self, final=False):
        uuid_cells = {} 
        for i, cell in enumerate(self.shared_cells):
            if cell['owner']:
                if cell['owner'] not in uuid_cells: uuid_cells[cell['owner']] = set()
                uuid_cells[cell['owner']].add(i)

        for uuid, indices in uuid_cells.items():
            if self._has_bingo_indices(indices):
                 await self.announce_winner(uuid, "BINGO! 5 in einer Reihe!")
                 return

        if final:
            max_count = 0
            winner = None
            for uuid, indices in uuid_cells.items():
                if len(indices) > max_count:
                    max_count = len(indices)
                    winner = uuid
            
            if winner:
                await self.announce_winner(winner, f"Meiste Items ({max_count})!")
            else:
                 await self.send(news("Unentschieden!"))
    
    def _has_bingo_indices(self, indices):
        # Rows
        for i in range(self.bingo_size):
            row_indices = set(range(i*self.bingo_size, (i+1)*self.bingo_size))
            if row_indices.issubset(indices): return True
        # Cols
        for i in range(self.bingo_size):
            col_indices = set(range(i, self.bingo_size*self.bingo_size, self.bingo_size))
            if col_indices.issubset(indices): return True
        # Diagonals
        d1_indices = set(i*self.bingo_size + i for i in range(self.bingo_size))
        if d1_indices.issubset(indices): return True
        d2_indices = set(i*self.bingo_size + (self.bingo_size-1-i) for i in range(self.bingo_size))
        if d2_indices.issubset(indices): return True
        return False

    async def announce_winner(self, uuid, reason):
        name = self.get_player_name(uuid)
        await self.send(news(f"GEWINNER: {name} - {reason}"))
        self.timer_active = False