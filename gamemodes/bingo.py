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
        self.free_center = config.get('free_center', False)
        
        # Shared board state. 
        # format: list of dicts: {'text': "Word", 'owners': set([uuid1, uuid2, ...])}
        self.shared_cells = [] 
        self.winners = set()
        self.bingo_counts = {} # uuid -> int
        
        self.timer_active = False
        self._loop_task = None
        self._initialized = False

    async def _send_state(self, uuid):
        await self.send(timer(self.timer_seconds), uuid)
        await super()._send_state(uuid)

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
        total_cells = self.bingo_size * self.bingo_size
        center_index = total_cells // 2
        has_free_center = self.free_center and (self.bingo_size % 2 == 1)
        needed = total_cells - 1 if has_free_center else total_cells

        if len(all_items) < needed:
             selection = all_items + ["?"] * (needed - len(all_items))
             random.shuffle(selection)
             items = selection[:needed]
        else:
            items = random.sample(all_items, needed)
        
        self.shared_cells = []
        item_idx = 0
        for i in range(total_cells):
            if has_free_center and i == center_index:
                self.shared_cells.append({"text": "FREI", "owners": set(), "is_free": True})
            else:
                self.shared_cells.append({"text": items[item_idx], "owners": set()})
                item_idx += 1
        
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
            
            is_free = cell.get('is_free', False)
            client_cells.append({
                "text": cell['text'],
                "done": is_free or (uuid in cell['owners']),
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
        if cell.get('is_free'):
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

        # Include free cells for everyone
        free_indices = {i for i, c in enumerate(self.shared_cells) if c.get('is_free')}
        if free_indices:
            for uid in user_indices:
                user_indices[uid] |= free_indices

        # Count bingos for everyone
        current_bingo_counts = {}
        for uid, indices in user_indices.items():
            current_bingo_counts[uid] = self._count_bingos(indices)

        # Check for new bingos (Mid-game)
        if not final:
            for uid, count in current_bingo_counts.items():
                if count > 0:
                    prev_count = self.bingo_counts.get(uid, 0)
                    if count > prev_count:
                        # New Bingo(s) found
                        self.bingo_counts[uid] = count
                        name = self.get_player_name(uid)
                        
                        if self.end_on_bingo:
                             await self.announce_winner(uid, "BINGO! 5 in einer Reihe!")
                             return
                        else:
                             await self.send(news(f"{name} hat ein BINGO! (Gesamt: {count})"))
            return

        # Final check (Timer ran out)
        max_bingos = 0
        if self.end_on_bingo:
            # Fallback to most items logic if game ended without bingo (e.g. manual timer stop? or timer runout without bingo)
            pass # Use standard most-items logic below
        else:
            # Special logic: Most Bingos, then Most Items
            if current_bingo_counts:
                max_bingos = max(current_bingo_counts.values())
            
            if max_bingos > 0:
                bingo_winners = [uid for uid, c in current_bingo_counts.items() if c == max_bingos]
                if len(bingo_winners) == 1:
                    await self.announce_winner(bingo_winners[0], f"Meiste Bingos ({max_bingos})!", stop_game=False)
                    return
                
                # Tie in bingos -> check items among the bingo winners
                # Filter user_indices to only bingo_winners
                user_indices = {uid: user_indices[uid] for uid in bingo_winners if uid in user_indices}
                # Fall through to "most items" logic with filtered list
            else:
                # No bingos at all -> Fall through to "most items" logic for everyone
                pass

        # Standard "Most Items" check (used for tie-breaking or no bingos)
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
            reason = f"Meiste Items ({max_count})!"
            if not self.end_on_bingo and max_bingos > 0:
                 reason = f"Meiste Bingos ({max_bingos}) & Items ({max_count})!"
            await self.announce_winner(winners[0], reason, stop_game=False)
        elif len(winners) > 1:
             names = [self.get_player_name(uid) for uid in winners]
             await self.send(news(f"Unentschieden: {', '.join(names)} ({max_count})"))

    def _count_bingos(self, indices):
        count = 0
        # Rows
        for i in range(self.bingo_size):
            row_indices = set(range(i*self.bingo_size, (i+1)*self.bingo_size))
            if row_indices.issubset(indices): count += 1
        # Cols
        for i in range(self.bingo_size):
            col_indices = set(range(i, self.bingo_size*self.bingo_size, self.bingo_size))
            if col_indices.issubset(indices): count += 1
        # Diagonals
        d1_indices = set(i*self.bingo_size + i for i in range(self.bingo_size))
        if d1_indices.issubset(indices): count += 1
        d2_indices = set(i*self.bingo_size + (self.bingo_size-1-i) for i in range(self.bingo_size))
        if d2_indices.issubset(indices): count += 1
        return count

    def _has_bingo_indices(self, indices):
        return self._count_bingos(indices) > 0

    async def announce_winner(self, uuid, reason, stop_game=True):
        name = self.get_player_name(uuid)
        await self.send(news(f"GEWINNER: {name} - {reason}"))
        if stop_game:
            self.timer_active = False
