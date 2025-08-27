#
# Client
#

def pair_result(pair_id, _item, is_new=False):
    if is_new:
        return {'type': 'pair_result', 'data': {"id": pair_id, "new_item": _item, "is_new": True}}
    return {'type': 'pair_result', 'data': {"id": pair_id, "new_item": _item}}


def pair_empty_result(pair_id):
    return {'type': 'pair_result', 'data': {"id": pair_id, "new_item": None}}


def news(message):
    return {'type': 'news', 'data': message}


def timer(time):
    if time is None:
        return {'type': 'timer'}
    return {'type': 'timer', 'data': time}


def gamemode(title):
    return {'type': 'mode', 'data': title}


def username(_username):
    return {'type': 'username', 'data': _username}


def players(_players):
    return {'type': 'players', 'data': _players}


def target(targets):
    return {'type': 'target', 'data': targets}


def item_list(items):
    return {'type': 'items', 'data': items}


def item(name, emoji):
    return {'name': name, 'emoji': emoji}


def error(message):
    return {'type': 'error', 'data': message}


def retry():
    return {'type': 'retry'}


def wrong_passphrase():
    return {'type': 'wrong_passphrase'}


def update_username(_username):
    return {'type': 'update_username', 'data': _username}


def clear():
    return {'type': 'clear'}


#
# Controller
#

def release():
    return {'type': 'release'}


def invalid_pass():
    return {'type': 'invalid_pass'}


def unauthorized():
    return {'type': 'unauthorized'}


def claimed():
    return {'type': 'claimed'}


def ask_llm(uuid, pair_id, item1, item2):
    return {'type': 'ask_llm', 'data': {'uuid': uuid, 'pair_id': pair_id, 'item1': item1, 'item2': item2}}
