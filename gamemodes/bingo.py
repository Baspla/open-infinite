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
        self.mode_name = "Bingo"
        self.bingo_size = int(config.get('size', 5))
        self.bingo_boards = {}  # uuid -> list of cell dicts
        self.timer_seconds = int(config.get('timer', 900))
        self.custom_words = config.get('words', [])
        self.free_center = config.get('free_center', False)
        self.timer_active = False
        self._loop_task = None

    async def start(self):
        await super().start()
        self._ensure_started()

    def _ensure_started(self):
        if not self.timer_active:
            self.timer_active = True
            if self.timer_seconds > 0 and (self._loop_task is None or self._loop_task.done()):
                self._loop_task = asyncio.create_task(self.game_loop())

    async def game_loop(self):
        while self.timer_active and self.timer_seconds > 0:
            minutes = self.timer_seconds // 60
            seconds = self.timer_seconds % 60
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

    def _generate_board(self):
        if self.custom_words:
            all_items = self.custom_words
        else:
            all_items = list(self.game_controller.cache.itemcache.keys())
        
        # Avoid empty or small cache issues
        if not all_items:
             return ["?"] * (self.bingo_size * self.bingo_size)
             
        if len(all_items) < self.bingo_size * self.bingo_size:
             selection = all_items + ["?"] * (self.bingo_size * self.bingo_size - len(all_items))
             # Don't shuffle strictly if not needed, but random sample is better
             random.shuffle(selection)
             return selection[:self.bingo_size * self.bingo_size]
        return random.sample(all_items, self.bingo_size * self.bingo_size)

    def get_bingo_field(self, uuid):
        self._ensure_started()
        if uuid not in self.bingo_boards:
            # Generate new board for this player
            items = self._generate_board()
            board = [{"text": item, "done": False} for item in items]
            
            if self.free_center and self.bingo_size % 2 == 1:
                center_idx = (self.bingo_size * self.bingo_size) // 2
                board[center_idx] = {"text": "FREE", "done": True}
            
            self.bingo_boards[uuid] = board
        
        return {
            "size": self.bingo_size,
            "cells": self.bingo_boards[uuid]
        }

    async def _add_item_and_notify(self, uuid, pair_id, new_item, cached):
        await super()._add_item_and_notify(uuid, pair_id, new_item, cached)
        await self.check_bingo_progress(uuid, new_item.get('name'))

    async def check_bingo_progress(self, uuid, item_name):
        board = self.bingo_boards.get(uuid)
        if not board:
            return

        changed = False
        for cell in board:
            if cell['text'] == item_name and not cell['done']:
                cell['done'] = True
                changed = True
        
        if changed:
            await self.send_bingo_field(uuid)
            await self.check_winner()

    async def check_winner(self, final=False):
        max_score = 0
        winner = None
        
        for uuid, board in self.bingo_boards.items():
            # Check standard Bingo (5 in row)
             if self._has_bingo(board):
                 await self.announce_winner(uuid, "BINGO! 5 in einer Reihe!")
                 return
             
             if final:
                count = sum(1 for c in board if c['done'])
                if count > max_score:
                    max_score = count
                    winner = uuid
        
        if final:
            if winner:
                await self.announce_winner(winner, f"Meiste Items ({max_score})!")
            else:
                await self.send(news("Unentschieden oder keine Treffer!"))

    def _has_bingo(self, board):
        # Rows
        for i in range(self.bingo_size):
            row = board[i*self.bingo_size : (i+1)*self.bingo_size]
            if all(c['done'] for c in row): return True
        # Cols
        for i in range(self.bingo_size):
            col = [board[r*self.bingo_size + i] for r in range(self.bingo_size)]
            if all(c['done'] for c in col): return True
        # Diagonals
        d1 = [board[i*self.bingo_size + i] for i in range(self.bingo_size)]
        if all(c['done'] for c in d1): return True
        d2 = [board[i*self.bingo_size + (self.bingo_size-1-i)] for i in range(self.bingo_size)]
        if all(c['done'] for c in d2): return True
        return False

    async def announce_winner(self, uuid, reason):
        name = self.get_player_name(uuid)
        await self.send(news(f"GEWINNER: {name} - {reason}"))
        self.timer_active = False
