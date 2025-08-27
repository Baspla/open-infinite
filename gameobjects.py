class Item:
    def __init__(self, name, emoji):
        self.name = name
        self.emoji = emoji
    
    def __eq__(self, other):
        return self.name == other.name
    
    def __hash__(self):
        return hash(self.name)
    
    def __repr__(self):
        return self.name
    
    def __str__(self):
        return self.name


class Combo:
    def __init__(self, item1, item2, result):
        self.item1 = item1
        self.item2 = item2
        self.result = result
    
    def __eq__(self, other):
        return self.item1 == other.item1 and self.item2 == other.item2
    
    def __hash__(self):
        return hash(self.item1) + hash(self.item2)
    
    def __repr__(self):
        return self.item1.name + ' + ' + self.item2.name + ' = ' + self.result.name
    
    def __str__(self):
        return self.item1.name + ' + ' + self.item2.name + ' = ' + self.result.name
