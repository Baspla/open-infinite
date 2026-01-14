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


def gamemode(title):
    return {'type': 'mode', 'data': title}


def username(_username):
    return {'type': 'username', 'data': _username}


def item_list(items):
    return {'type': 'items', 'data': items}


def item(name, emoji):
    return {'name': name, 'emoji': emoji}


def error(message):
    return {'type': 'error', 'data': message}


def retry():
    return {'type': 'retry'}


def clear():
    return {'type': 'clear'}
