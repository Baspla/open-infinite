import logging

from server import start_server

log = logging.getLogger('main')


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    )
    logging.getLogger('socketio').setLevel(logging.DEBUG)
    logging.getLogger('socketio.server').setLevel(logging.DEBUG)
    logging.getLogger('engineio').setLevel(logging.DEBUG)
    logging.getLogger('engineio.server').setLevel(logging.DEBUG)
    log.info('Server started')
    start_server()