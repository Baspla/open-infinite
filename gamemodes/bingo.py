import asyncio
import logging
import random
from gamemodes.classic import ClassicGamemode
from templates import bingo, news, timer

log = logging.getLogger('BingoGamemode')

class BingoGamemode(ClassicGamemode):
    def __init__(self, game_controller, config=None):
        super().__init__(game_controller)
        config = config or {}
        
        self.lockout = config.get('lockout', False)
        self.manual_mode = config.get('manual', True)
        self.end_on_bingo = config.get('end_on_bingo', False)

        parts = []
        if self.lockout: parts.append("Lockout")
        parts.append("Bingo")
        parts.append("(Manual)" if self.manual_mode else "(Auto)")
        self.mode_name = " ".join(parts)
        
        self.bingo_size = int(config.get('size', 5))
        self.timer_seconds = int(config.get('timer', 900))
        self.custom_words = config.get('words', [])
        
        # Shared board state. 
        # format: list of dicts: {'text': "Word", 'owners': set([uuid1, uuid2, ...])}
        self.shared_cells = [] 
        self.winners = set()
        
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
             self.shared_cells = [{"text": "?", "owners": set()} for _ in range(self.bingo_size**2)]
             return 

        # Generate board items
        needed = self.bingo_size * self.bingo_size
        if len(all_items) < needed:
             selection = all_items + ["?"] * (needed - len(all_items))
             random.shuffle(selection)
             items = selection[:needed]
        else:
            items = random.sample(all_items, needed)
        
        self.shared_cells = [{"text": i, "owners": set()} for i in items]
        self._initialized = True

    def _ensure_started(self):
         if not self.timer_active:
            self.timer_active = True
            if self.timer_seconds > 0 and (self._loop_task is None or self._loop_task.done()):
                self._loop_task = asyncio.create_task(self.game_loop())

    async def game_loop(self):
        while self.timer_active and self.timer_seconds > 0:
            try:
                if self.timer_seconds % 60 == 0 or self.timer_seconds <= 10:
                    await self.send(timer(self.timer_seconds))
            except Exception as e:
                log.error(f"Error in game loop: {e}")
            await asyncio.sleep(1)
            self.timer_seconds -= 1
        
        if self.timer_active:
             await self.send(timer(0))
             await self.send(news("Zeit abgelaufen!"))
             await self.check_winner(final=True)
             self.timer_active = False

    async def stop(self):
        self.timer_active = False
        if self._loop_task:
            self._loop_task.cancel()
        await super().stop()

    def _get_player_color(self, uuid):
        p = self.game_controller.players.get(uuid)
        return p.color if p else "#888888"

    def get_bingo_field(self, uuid):
        self._ensure_initialized()
        self._ensure_started()
        
        client_cells = []
        for cell in self.shared_cells:
            owners = list(cell['owners'])
            done_colors = [self._get_player_color(uid) for uid in owners]
            
            client_cells.append({
                "text": cell['text'],
                "done": uuid in cell['owners'],
                "done_colors": done_colors,
                "done_color": done_colors[0] if done_colors else None 
            })
            
        return {
            "size": self.bingo_size,
            "cells": client_cells
        }

    async def handle_bingo_click(self, uuid, click_data):
        if not self.manual_mode:
            return 

        self._ensure_initialized()
        self._ensure_started()
        
        index = click_data.get('index')
        if index is None or index < 0 or index >= len(self.shared_cells):
            return
            
        cell = self.shared_cells[index]
        item_name = cell['text']
        
        # Verify ownership (User must have found the item)
        pool = self.get_item_pool(uuid)
        has_item = any(i.get('name') == item_name for i in pool)
        
        if not has_item:
            return

        # Toggle logic
        changed = False
        if uuid in cell['owners']:
             cell['owners'].remove(uuid)
             changed = True
        else:
             # Toggle On - Check Lockout
             if self.lockout and len(cell['owners']) > 0:
                 return # Locked out
             
             cell['owners'].add(uuid)
             changed = True
             
        if changed:
            await self.broadcast_bingo_field()
            await self.check_winner(final=False)

    async def _add_item_and_notify(self, uuid, pair_id, new_item, cached):
        # Call super to add to inventory and notify user of pair result
        await super()._add_item_and_notify(uuid, pair_id, new_item, cached)
        # Check bingo logic
        if not self.manual_mode:
            await self.check_bingo_progress(uuid, new_item.get('name'))

    async def check_bingo_progress(self, uuid, item_name):
        changed = False
        for cell in self.shared_cells:
            if cell['text'] == item_name:
                # If already owned by this user, ignore
                if uuid in cell['owners']:
                    continue
                
                # Check Lockout rules
                if self.lockout and len(cell['owners']) > 0:
                    # Already owned by someone else
                    continue
                
                cell['owners'].add(uuid)
                changed = True
        
        if changed:
            await self.broadcast_bingo_field()
            await self.check_winner()

    async def check_winner(self, final=False):
        user_indices = {}
        for idx, cell in enumerate(self.shared_cells):
            for owner in cell['owners']:
                if owner not in user_indices: user_indices[owner] = set()
                user_indices[owner].add(idx)

        for uid, indices in user_indices.items():
            if uid in self.winners:
                continue

            if self._has_bingo_indices(indices):
                 self.winners.add(uid)
                 await self.announce_winner(uid, "BINGO! 5 in einer Reihe!", stop_game=self.end_on_bingo)
                 if self.end_on_bingo:
                     return

        if final:
            max_count = 0
            winners = []
            for uid, indices in user_indices.items():
                count = len(indices)
                if count > max_count:
                    max_count = count
                    winners = [uid]
                elif count == max_count:
                    winners.append(uid)
            
            if len(winners) == 1:
                await self.announce_winner(winners[0], f"Meiste Items ({max_count})!", stop_game=False)
            elif len(winners) > 1:
                 names = [self.get_player_name(uid) for uid in winners]
                 await self.send(news(f"Unentschieden: {', '.join(names)} ({max_count})"))
            else:
                 await self.send(news("Keine Treffer!"))

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

    async def announce_winner(self, uuid, reason, stop_game=True):
        name = self.get_player_name(uuid)
        await self.send(news(f"GEWINNER: {name} - {reason}"))
        if stop_game:
            self.timer_active = False
