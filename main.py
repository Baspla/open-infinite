import logging
from game import GameController
from server import start_server

log = logging.getLogger('main')

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    log.info('Server started')
    game_controller = GameController()
    start_server(game_controller)