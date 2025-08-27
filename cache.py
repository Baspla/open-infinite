import json


class Cache:
    def __init__(self):
        self.combocache = {}
        self.itemcache = {}
        pass

    def get(self, key):
        if not self.combocache.get(key):
            return None
        result = self.combocache.get(key)
        emoji = self.itemcache.get(result)
        return {"name": result, "emoji": emoji}
    
    def addPair(self, key, value):
        self.combocache[key] = value
        pass

    def addItem(self, key, value):
        if not self.itemcache.get(key):
            self.itemcache[key] = [value]
        else:
            return self.itemcache[key]
    
    def load(self, filename):
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                self.combocache = data.get('combocache', {})
                self.itemcache = data.get('itemcache', {})
        except FileNotFoundError:
            print(f"No such file: {filename}")
        except json.JSONDecodeError:
            print(f"Error decoding JSON from file: {filename}")
    
    def save(self, filename):
        data = {
            'combocache': self.combocache,
            'itemcache': self.itemcache
        }
        with open(filename, 'w') as f:
            json.dump(data, f)
        