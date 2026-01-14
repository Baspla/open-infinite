import logging

from server import start_server

log = logging.getLogger('main')


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    log.info('Server started')
    start_server()