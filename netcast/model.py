class ModelStack:
    def __init__(self):
        self.fields = []

    def push(self, item):
        self.fields.append(item)

    def pop(self, index):
        self.fields.pop(index)

    def clear(self, index):
        self.fields.clear()
